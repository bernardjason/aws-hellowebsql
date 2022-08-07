# Copyright 2017-2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file
# except in compliance with the License. A copy of the License is located at
#
#     http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is distributed on an "AS IS"
# BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under the License.

# https://github.com/awslabs/aws-support-tools/blob/master/Cognito/decode-verify-jwt/decode-verify-jwt.py
import json
import os
import re
import time
import traceback
import urllib.request

from jose import jwk, jwt
from jose.utils import base64url_decode


if __name__ == '__main__':
    os.environ['region'] = 'us-east-1'
    os.environ['userpool_id'] = 'us-east-1_8BpsjndmZ'
    os.environ['app_client_id'] = '747av9n8svnb1vm1bc5futjvvh'

region = os.environ['region']
userpool_id = os.environ['userpool_id']
app_client_id = os.environ['app_client_id']

keys_url = 'https://cognito-idp.{}.amazonaws.com/{}/.well-known/jwks.json'.format(region, userpool_id)
with urllib.request.urlopen(keys_url) as f:
    response = f.read()
keys = json.loads(response.decode('utf-8'))['keys']


def lambda_handler(event, context):
    try:
        token=""

        if "authorization" in event['headers']:
            token = event['headers']["authorization"]

        if "Authorization" in event['headers']:
            token = event['headers']["Authorization"]

        #print("token is",token)
        headers = jwt.get_unverified_headers(token)
        kid = headers['kid']
        # search for the kid in the downloaded public keys
        key_index = -1
        for i in range(len(keys)):
            if kid == keys[i]['kid']:
                key_index = i
                break
        if key_index == -1:
            raise Exception('Public key not found in jwks.json')

        #print("Found ",jwk.construct(keys[key_index]))

        public_key = jwk.construct(keys[key_index])
        message, encoded_signature = str(token).rsplit('.', 1)
        decoded_signature = base64url_decode(encoded_signature.encode('utf-8'))

        if not public_key.verify(message.encode("utf8"), decoded_signature):
            raise Exception('Signature verification failed')

        #print('Signature successfully verified')
        claims = jwt.get_unverified_claims(token)
        if time.time() > claims['exp']:
            raise Exception('Token is expired')
        if 'aud' in claims and claims['aud'] != app_client_id:
            raise Exception('Token was not issued for this audience')

        print("claims",claims)
        principalId = claims['username']

        if "methodArn" in event:
            tmp = event['methodArn'].split(':')
            apiGatewayArnTmp = tmp[5].split('/')
            awsAccountId = tmp[4]
            policy = AuthPolicy(principalId, awsAccountId)
            policy.restApiId = apiGatewayArnTmp[0]
            policy.region = tmp[3]
            policy.stage = apiGatewayArnTmp[1]
        else:
            raise Exception('bad request')

        policy.allowAllMethods()
        authResponse = policy.build()

        return authResponse
    except Exception:
        policy = AuthPolicy("na","na")
        print(traceback.format_exc())
        policy.denyAllMethods()
        authResponse = policy.build()
        context = {
            'key': 'value', # $context.authorizer.key -> value
            'number' : 1,
            'bool' : True
        }
        authResponse['context'] = context
        print(authResponse)
        return authResponse

class HttpVerb:
    GET     = "GET"
    POST    = "POST"
    PUT     = "PUT"
    PATCH   = "PATCH"
    HEAD    = "HEAD"
    DELETE  = "DELETE"
    OPTIONS = "OPTIONS"
    ALL     = "*"

class AuthPolicy(object):
    awsAccountId = ""
    """The AWS account id the policy will be generated for. This is used to create the method ARNs."""
    principalId = ""
    """The principal used for the policy, this should be a unique identifier for the end user."""
    version = "2012-10-17"
    """The policy version used for the evaluation. This should always be '2012-10-17'"""
    pathRegex = "^[/.a-zA-Z0-9-\*]+$"
    """The regular expression used to validate resource paths for the policy"""

    """these are the internal lists of allowed and denied methods. These are lists
    of objects and each object has 2 properties: A resource ARN and a nullable
    conditions statement.
    the build method processes these lists and generates the approriate
    statements for the final policy"""
    allowMethods = []
    denyMethods = []


    restApiId = "<<restApiId>>"
    """ Replace the placeholder value with a default API Gateway API id to be used in the policy. 
    Beware of using '*' since it will not simply mean any API Gateway API id, because stars will greedily expand over '/' or other separators. 
    See https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_resource.html for more details. """

    region = "<<region>>"
    """ Replace the placeholder value with a default region to be used in the policy. 
    Beware of using '*' since it will not simply mean any region, because stars will greedily expand over '/' or other separators. 
    See https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_resource.html for more details. """

    stage = "<<stage>>"
    """ Replace the placeholder value with a default stage to be used in the policy. 
    Beware of using '*' since it will not simply mean any stage, because stars will greedily expand over '/' or other separators. 
    See https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_resource.html for more details. """

    def __init__(self, principal, awsAccountId):
        self.awsAccountId = awsAccountId
        self.principalId = principal
        self.allowMethods = []
        self.denyMethods = []

    def _addMethod(self, effect, verb, resource, conditions):
        """Adds a method to the internal lists of allowed or denied methods. Each object in
        the internal list contains a resource ARN and a condition statement. The condition
        statement can be null."""
        if verb != "*" and not hasattr(HttpVerb, verb):
            raise NameError("Invalid HTTP verb " + verb + ". Allowed verbs in HttpVerb class")
        resourcePattern = re.compile(self.pathRegex)
        if not resourcePattern.match(resource):
            raise NameError("Invalid resource path: " + resource + ". Path should match " + self.pathRegex)

        if resource[:1] == "/":
            resource = resource[1:]

        resourceArn = ("arn:aws:execute-api:" +
                       self.region + ":" +
                       self.awsAccountId + ":" +
                       self.restApiId + "/" +
                       self.stage + "/" +
                       verb + "/" +
                       resource)

        if effect.lower() == "allow":
            self.allowMethods.append({
                'resourceArn' : resourceArn,
                'conditions' : conditions
            })
        elif effect.lower() == "deny":
            self.denyMethods.append({
                'resourceArn' : resourceArn,
                'conditions' : conditions
            })

    def _getEmptyStatement(self, effect):
        """Returns an empty statement object prepopulated with the correct action and the
        desired effect."""
        statement = {
            'Action': 'execute-api:Invoke',
            'Effect': effect[:1].upper() + effect[1:].lower(),
            'Resource': []
        }

        return statement

    def _getStatementForEffect(self, effect, methods):
        """This function loops over an array of objects containing a resourceArn and
        conditions statement and generates the array of statements for the policy."""
        statements = []

        if len(methods) > 0:
            statement = self._getEmptyStatement(effect)

            for curMethod in methods:
                if curMethod['conditions'] is None or len(curMethod['conditions']) == 0:
                    statement['Resource'].append(curMethod['resourceArn'])
                else:
                    conditionalStatement = self._getEmptyStatement(effect)
                    conditionalStatement['Resource'].append(curMethod['resourceArn'])
                    conditionalStatement['Condition'] = curMethod['conditions']
                    statements.append(conditionalStatement)

            statements.append(statement)

        return statements

    def allowAllMethods(self):
        """Adds a '*' allow to the policy to authorize access to all methods of an API"""
        self._addMethod("Allow", HttpVerb.ALL, "*", [])

    def denyAllMethods(self):
        """Adds a '*' allow to the policy to deny access to all methods of an API"""
        self._addMethod("Deny", HttpVerb.ALL, "*", [])

    def allowMethod(self, verb, resource):
        """Adds an API Gateway method (Http verb + Resource path) to the list of allowed
        methods for the policy"""
        self._addMethod("Allow", verb, resource, [])

    def denyMethod(self, verb, resource):
        """Adds an API Gateway method (Http verb + Resource path) to the list of denied
        methods for the policy"""
        self._addMethod("Deny", verb, resource, [])

    def allowMethodWithConditions(self, verb, resource, conditions):
        """Adds an API Gateway method (Http verb + Resource path) to the list of allowed
        methods and includes a condition for the policy statement. More on AWS policy
        conditions here: http://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements.html#Condition"""
        self._addMethod("Allow", verb, resource, conditions)

    def denyMethodWithConditions(self, verb, resource, conditions):
        """Adds an API Gateway method (Http verb + Resource path) to the list of denied
        methods and includes a condition for the policy statement. More on AWS policy
        conditions here: http://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements.html#Condition"""
        self._addMethod("Deny", verb, resource, conditions)

    def build(self):
        """Generates the policy document based on the internal lists of allowed and denied
        conditions. This will generate a policy with two main statements for the effect:
        one statement for Allow and one statement for Deny.
        Methods that includes conditions will have their own statement in the policy."""
        if ((self.allowMethods is None or len(self.allowMethods) == 0) and
                (self.denyMethods is None or len(self.denyMethods) == 0)):
            raise NameError("No statements defined for the policy")

        policy = {
            'principalId' : self.principalId,
            'policyDocument' : {
                'Version' : self.version,
                'Statement' : []
            }
        }

        policy['policyDocument']['Statement'].extend(self._getStatementForEffect("Allow", self.allowMethods))
        policy['policyDocument']['Statement'].extend(self._getStatementForEffect("Deny", self.denyMethods))

        return policy

if __name__ == '__main__':


    token = "eyJraWQiOiJDMWtXTzZMbWV0RW1qTEM1SSs5NTN1QzBOSklUaVRtRFwvZHpkeExhN0VCcz0iLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiI5NmZiYzVhMS1hN2MwLTQwZWMtYTZhMi05YTRmMGVmNjU4MDYiLCJ0b2tlbl91c2UiOiJhY2Nlc3MiLCJzY29wZSI6ImF3cy5jb2duaXRvLnNpZ25pbi51c2VyLmFkbWluIG9wZW5pZCIsImF1dGhfdGltZSI6MTY1Nzk1Mzg4MCwiaXNzIjoiaHR0cHM6XC9cL2NvZ25pdG8taWRwLnVzLWVhc3QtMS5hbWF6b25hd3MuY29tXC91cy1lYXN0LTFfOEJwc2puZG1aIiwiZXhwIjoxNjU3OTU3NDgwLCJpYXQiOjE2NTc5NTM4ODAsInZlcnNpb24iOjIsImp0aSI6IjZjMzEzYjdhLWVhN2ItNDhhMC04NDZmLTJiNTkyYTA4YmM2MiIsImNsaWVudF9pZCI6Ijc0N2F2OW44c3ZuYjF2bTFiYzVmdXRqdnZoIiwidXNlcm5hbWUiOiJiZXJuYXJkY2phc29uQGdtYWlsLmNvbSJ9.yrGSfWXqbLrh5uVlu8QxEALhmusUguBjYvzkKUOqAU8MmK6EZyg3FpPP8i0gzIY3awi90MU9Zqlnm-N1ChTNBhci5SyXHkxVym2zp1VbVWz5NLTEa_67l2SgpCBc-QMsaJ4AbFumoj425zzKzo0oTX3EAlbdo79vzllbZlFOJwslpvS8ZDEtwZOqi0aHAOn85DDrmxtmrbkIX5i9kDzMSFT1mTXCcuT78WLgqPxaGloG2dZ6-ZDykzbvSWlmL_kPJQ9d-fktnArpDvW23Bb_XBA4l_bczAUidUgq91lbb3fIWt-yupE4fzZwHwXMJVJyb-g1rLw5Z7tYKGca5B9Ytw"
    event = {
        "headers": {
            "authorization": token,
        },
        "methodArn":"1/1/1:1/1/1:1/1/1:1/1/1/1:1/1/1/1/1/:1/1/1/1/"
    }
    #print(base64url_decode(token+"===="))
    lambda_handler(event,None)