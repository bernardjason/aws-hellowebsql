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
import time
import traceback
import urllib.request

from jose import jwk, jwt
from jose.utils import base64url_decode

region = 'us-east-1'
userpool_id = 'us-east-1_L2bdp5WK7'
app_client_id = '2nqn6mis45qqvfmhkina4o619g='

keys_url = 'https://cognito-idp.{}.amazonaws.com/{}/.well-known/jwks.json'.format(region, userpool_id)
# instead of re-downloading the public keys every time
# we download them only on cold start
# https://aws.amazon.com/blogs/compute/container-reuse-in-lambda/
with urllib.request.urlopen(keys_url) as f:
    response = f.read()
keys = json.loads(response.decode('utf-8'))['keys']

bad = {
    "status": "401",
    "statusDescription": "Unauthorized"
}



def lambda_handler(event, context):
    try:
        print(event)
        request = event['Records'][0]['cf']['request']
        # cf = event['Records'][0]['cf']
        headers = request['headers']
        token = "bad"
        for cookie in headers.get('cookie', []):
            if 'authorization' in cookie['value']:
                cookies = (dict(i.split('=') for i in cookie['value'].split('; ')))
                token = cookies['authorization']
                break

        # token = request['headers']['authorization'][0]['value'][7:]
        print(token)

        # access_token=request['querystring'].partition("access_token=")
        # token=access_token[-1].split("&")[0]

        # get the kid from the headers prior to verification
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
        # construct the public key
        public_key = jwk.construct(keys[key_index])
        # get the last two sections of the token,
        # message and signature (encoded in base64)
        message, encoded_signature = str(token).rsplit('.', 1)
        # decode the signature
        decoded_signature = base64url_decode(encoded_signature.encode('utf-8'))
        # verify the signature
        if not public_key.verify(message.encode("utf8"), decoded_signature):
            raise Exception('Signature verification failed')
        print('Signature successfully verified')
        # since we passed the verification, we can now safely
        # use the unverified claims
        claims = jwt.get_unverified_claims(token)
        # additionally we can verify the token expiration
        if time.time() > claims['exp']:
            raise Exception('Token is expired')
        # and the Audience  (use claims['client_id'] if verifying an access token)
        if 'aud' in claims and claims['aud'] != app_client_id:
            raise Exception('Token was not issued for this audience')
        # now we can use the claims

        # request = event["Records"][0]["cf"]["request"]
        # del request["headers"]["authorization"]
        return request
    except Exception:
        print(traceback.format_exc())
        return bad


if __name__ == '__main__':
    event = {
        "Records": [
            {
                "cf": {
                    "request": {
                        "headers": {
                            "host": [
                                {
                                    "key": "Host",
                                    "value": "d111111abcdef8.cloudfront.net"
                                }
                            ],
                            "cookie": [
                                {
                                    "key": "cookie",
                                    "value": "authorization=eyJraWQiOiJDMWtXTzZMbWV0RW1qTEM1SSs5NTN1QzBOSklUaVRtRFwvZHpkeExhN0VCcz0iLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiI5NmZiYzVhMS1hN2MwLTQwZWMtYTZhMi05YTRmMGVmNjU4MDYiLCJpc3MiOiJodHRwczpcL1wvY29nbml0by1pZHAudXMtZWFzdC0xLmFtYXpvbmF3cy5jb21cL3VzLWVhc3QtMV84QnBzam5kbVoiLCJ2ZXJzaW9uIjoyLCJjbGllbnRfaWQiOiI3NDdhdjluOHN2bmIxdm0xYmM1ZnV0anZ2aCIsImV2ZW50X2lkIjoiMTZkOWFlNTYtMzQ5YS00ZWJlLWEzNDEtNjZkMWQxYjEwOTI2IiwidG9rZW5fdXNlIjoiYWNjZXNzIiwic2NvcGUiOiJhd3MuY29nbml0by5zaWduaW4udXNlci5hZG1pbiBvcGVuaWQiLCJhdXRoX3RpbWUiOjE2NTgwMzg4MTYsImV4cCI6MTY1ODA0MjQxNiwiaWF0IjoxNjU4MDM4ODE2LCJqdGkiOiJkNjk0OWI1MC0xNGU0LTQ5ZjUtYThmYi04OWQ3YzBiODRjOWYiLCJ1c2VybmFtZSI6ImJlcm5hcmRjamFzb25AZ21haWwuY29tIn0.DdNAcHqvsa4khKS_WIMVMUFxKSCJjLEC0PdzkM9yslI_l0TR5XTnUapHlonrvpGurOCymrIEyeoyn6pRxmiv9OrI99WRSQZe557ioBlbYvZR9C5C9BcnGrGRVYzMIYS4dTcNwqMziNx1HsfHzgcf1yC1UPtkipmUunF6T4uKxXl4PQ2ghFIE35SDQnsAW6SOeAJO4b3X1oXjExwa4qAwBpKfPOEEzNKGc-uq32EA9GZ528S-6MpGDbBBzkqjfvD64_c-HQFuSGXzQyj_5fW0epsy5ENgz5MnOevjUwOGhkyOlpaJsED6T70pxyx7lfWTmKiLObJWnpMu5yIWBfDsug"+
                                    ""
                                }

                            ],
                            "user-agent": [
                                {
                                    "key": "User-Agent",
                                    "value": "curl/7.51.0"
                                }
                            ]
                        },
                        "clientIp": "2001:cdba::3257:9652",
                        "fred": "eyJraWQiOiJDMWtXTzZMbWV0RW1qTEM1SSs5NTN1QzBOSklUaVRtRFwvZHpkeExhN0VCcz0iLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiI5NmZiYzVhMS1hN2MwLTQwZWMtYTZhMi05YTRmMGVmNjU4MDYiLCJpc3MiOiJodHRwczpcL1wvY29nbml0by1pZHAudXMtZWFzdC0xLmFtYXpvbmF3cy5jb21cL3VzLWVhc3QtMV84QnBzam5kbVoiLCJ2ZXJzaW9uIjoyLCJjbGllbnRfaWQiOiI3NDdhdjluOHN2bmIxdm0xYmM1ZnV0anZ2aCIsImV2ZW50X2lkIjoiMGMyZTZkM2QtNjdjMy00MmUwLThhYzUtNGEwNTgwYzQyYzYxIiwidG9rZW5fdXNlIjoiYWNjZXNzIiwic2NvcGUiOiJhd3MuY29nbml0by5zaWduaW4udXNlci5hZG1pbiBvcGVuaWQiLCJhdXRoX3RpbWUiOjE2NTc5NjA4MzYsImV4cCI6MTY1Nzk2NDQzNiwiaWF0IjoxNjU3OTYwODM3LCJqdGkiOiI5ZDFlOGYzYS1iMTdiLTRjMWItYTEwNi1lYzAxN2VkODJiOGIiLCJ1c2VybmFtZSI6ImJlcm5hcmRjamFzb25AZ21haWwuY29tIn0.e_vK91PQcf6wYCa4Q4WeVciesk37j7mxejAg7FAjC-F2J5eS_vEGOpelU5PGXwH-CiRoY3FQjAn64zs2K-zkLStIbYqNI7E1TDAX1qL30qyOi3PRUakhLBjT6cbe8S4geMdazkKCl_Lrirh77kwcv9i0xWHr8cCy6AoHmnniW9zXIoLaztxeyL9O1h_5YnikWEp5X-SXMUXJvkK_lWbgo9VYjk1fSwtni38P_EZB5sAT4pDLgUarUktXxP7zKRXmIQB5Cv6Hc0tv--YPYgpLdXOzWmvwWNea3I5Ua3bZBgRkNbPpWYrkTfso0dxGixwQ5iqKc725xrqyoPWdsRrZEg",
                        "xuri": "In0.eyJhdF9oYXNoIjoial9VMmRiUlQyMUJMMTFFSmJpNXRtdyIsInN1YiI6Ijk2ZmJjNWExLWE3YzAtNDBlYy1hNmEyLTlhNGYwZWY2NTgwNiIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJpc3MiOiJodHRwczpcL1wvY29nbml0by1pZHAudXMtZWFzdC0xLmFtYXpvbmF3cy5jb21cL3VzLWVhc3QtMV84QnBzam5kbVoiLCJjb2duaXRvOnVzZXJuYW1lIjoiYmVybmFyZGNqYXNvbkBnbWFpbC5jb20iLCJhdWQiOiI3NDdhdjluOHN2bmIxdm0xYmM1ZnV0anZ2aCIsImV2ZW50X2lkIjoiZjA2NWZkZTMtYmNiMS00YWYzLTlmZDMtZTQ4NWNlNDdmOWRhIiwidG9rZW5fdXNlIjoiaWQiLCJhdXRoX3RpbWUiOjE2NTc5ODcyMjEsImV4cCI6MTY1Nzk5MDgyMSwiaWF0IjoxNjU3OTg3MjIxLCJqdGkiOiI4YzEzZTVkYi1lZTU2LTQ0YjctYTRjMS02N2VlMzhiNTM0YzAiLCJlbWFpbCI6ImJlcm5hcmRjamFzb25AZ21haWwuY29tIn0.fsBrnGWcB1iBaMzZ0TA0mUy9KVxBJYxOGVZVeA_LV1PrSOiCECIoG4KUeExbAkzIU98ym_obrr8bMTRosD-y3p6n8Shb5zBtZGVSLI_bx8_IaGSNEufeLflP3OTMkPfP_lqT6ChioySyCyKOXZjr53jeBeH_ZZuUIUMuXZzRTaUQHiAoOo2gH7HOBIc3FgAO-eH8vTAb3a3mZw3wwdxfDCrIQv9lmfBxuNki5ThRbx0PtBh09MpQ-9z7-exuluG6SjfZn3CfE_tb9tuGJb-ly5jLcWF4V6zzd4qUbDBodHfJ536SAwM68C8OB4FFAXMQAW3fKi1FBZV5KeNZTTriWQ&access_token=eyJraWQiOiJDMWtXTzZMbWV0RW1qTEM1SSs5NTN1QzBOSklUaVRtRFwvZHpkeExhN0VCcz0iLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiI5NmZiYzVhMS1hN2MwLTQwZWMtYTZhMi05YTRmMGVmNjU4MDYiLCJpc3MiOiJodHRwczpcL1wvY29nbml0by1pZHAudXMtZWFzdC0xLmFtYXpvbmF3cy5jb21cL3VzLWVhc3QtMV84QnBzam5kbVoiLCJ2ZXJzaW9uIjoyLCJjbGllbnRfaWQiOiI3NDdhdjluOHN2bmIxdm0xYmM1ZnV0anZ2aCIsImV2ZW50X2lkIjoiZjA2NWZkZTMtYmNiMS00YWYzLTlmZDMtZTQ4NWNlNDdmOWRhIiwidG9rZW5fdXNlIjoiYWNjZXNzIiwic2NvcGUiOiJhd3MuY29nbml0by5zaWduaW4udXNlci5hZG1pbiBvcGVuaWQiLCJhdXRoX3RpbWUiOjE2NTc5ODcyMjEsImV4cCI6MTY1Nzk5MDgyMSwiaWF0IjoxNjU3OTg3MjIxLCJqdGkiOiJkOTVjZDFjYi1lZTNmLTQ5ZmItOGJlMi1mZGE0M2NlYmY2NzciLCJ1c2VybmFtZSI6ImJlcm5hcmRjamFzb25AZ21haWwuY29tIn0.CmgdL2dHdwo4EwZaq4O6upz0uIrEdkR1z8My4eHkfuJjzsT45YyNOR3iocJVzRKEE22IxH19OKc62V9Qf2hDRFcfKXYAMzO7F_L695zy5nJP_HycE3ck9WwuLUTYQO7Mht1IM15Gg57yDFgvfuK4eh4wyn9jJtV3kcJY5_SMCxFnzyKbgJFmH40md6yYoS7Xx1ROtp1y6vlzxpXIHIl21992ptpmbKFIUQ2ac71V63bq-3UHi9ZExGgRYaGuqzvpwxLl_JI98DrwVbNy3xezZL_j5iLn8Y9EB30GCDMlNPNY9z08uJfT-HS6ll0EgJQZ2B01VdnF0qd7AYQKTd_gxQ&expires_in=3600&token_type=Bearer",
                        "xuri": "https://d3ph0bctzyxdp9.cloudfront.net/private/index.html#id_token=eyJraWQiOiJqOW9tekxqQVpNSDhDTXhOWXROSFNTTlhvNWNiWUpLVGpVendaRUlOOExvPSIsImFsZyI6IlJTMjU2In0.eyJhdF9oYXNoIjoial9VMmRiUlQyMUJMMTFFSmJpNXRtdyIsInN1YiI6Ijk2ZmJjNWExLWE3YzAtNDBlYy1hNmEyLTlhNGYwZWY2NTgwNiIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJpc3MiOiJodHRwczpcL1wvY29nbml0by1pZHAudXMtZWFzdC0xLmFtYXpvbmF3cy5jb21cL3VzLWVhc3QtMV84QnBzam5kbVoiLCJjb2duaXRvOnVzZXJuYW1lIjoiYmVybmFyZGNqYXNvbkBnbWFpbC5jb20iLCJhdWQiOiI3NDdhdjluOHN2bmIxdm0xYmM1ZnV0anZ2aCIsImV2ZW50X2lkIjoiZjA2NWZkZTMtYmNiMS00YWYzLTlmZDMtZTQ4NWNlNDdmOWRhIiwidG9rZW5fdXNlIjoiaWQiLCJhdXRoX3RpbWUiOjE2NTc5ODcyMjEsImV4cCI6MTY1Nzk5MDgyMSwiaWF0IjoxNjU3OTg3MjIxLCJqdGkiOiI4YzEzZTVkYi1lZTU2LTQ0YjctYTRjMS02N2VlMzhiNTM0YzAiLCJlbWFpbCI6ImJlcm5hcmRjamFzb25AZ21haWwuY29tIn0.fsBrnGWcB1iBaMzZ0TA0mUy9KVxBJYxOGVZVeA_LV1PrSOiCECIoG4KUeExbAkzIU98ym_obrr8bMTRosD-y3p6n8Shb5zBtZGVSLI_bx8_IaGSNEufeLflP3OTMkPfP_lqT6ChioySyCyKOXZjr53jeBeH_ZZuUIUMuXZzRTaUQHiAoOo2gH7HOBIc3FgAO-eH8vTAb3a3mZw3wwdxfDCrIQv9lmfBxuNki5ThRbx0PtBh09MpQ-9z7-exuluG6SjfZn3CfE_tb9tuGJb-ly5jLcWF4V6zzd4qUbDBodHfJ536SAwM68C8OB4FFAXMQAW3fKi1FBZV5KeNZTTriWQ&access_token=eyJraWQiOiJDMWtXTzZMbWV0RW1qTEM1SSs5NTN1QzBOSklUaVRtRFwvZHpkeExhN0VCcz0iLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiI5NmZiYzVhMS1hN2MwLTQwZWMtYTZhMi05YTRmMGVmNjU4MDYiLCJpc3MiOiJodHRwczpcL1wvY29nbml0by1pZHAudXMtZWFzdC0xLmFtYXpvbmF3cy5jb21cL3VzLWVhc3QtMV84QnBzam5kbVoiLCJ2ZXJzaW9uIjoyLCJjbGllbnRfaWQiOiI3NDdhdjluOHN2bmIxdm0xYmM1ZnV0anZ2aCIsImV2ZW50X2lkIjoiZjA2NWZkZTMtYmNiMS00YWYzLTlmZDMtZTQ4NWNlNDdmOWRhIiwidG9rZW5fdXNlIjoiYWNjZXNzIiwic2NvcGUiOiJhd3MuY29nbml0by5zaWduaW4udXNlci5hZG1pbiBvcGVuaWQiLCJhdXRoX3RpbWUiOjE2NTc5ODcyMjEsImV4cCI6MTY1Nzk5MDgyMSwiaWF0IjoxNjU3OTg3MjIxLCJqdGkiOiJkOTVjZDFjYi1lZTNmLTQ5ZmItOGJlMi1mZGE0M2NlYmY2NzciLCJ1c2VybmFtZSI6ImJlcm5hcmRjamFzb25AZ21haWwuY29tIn0.CmgdL2dHdwo4EwZaq4O6upz0uIrEdkR1z8My4eHkfuJjzsT45YyNOR3iocJVzRKEE22IxH19OKc62V9Qf2hDRFcfKXYAMzO7F_L695zy5nJP_HycE3ck9WwuLUTYQO7Mht1IM15Gg57yDFgvfuK4eh4wyn9jJtV3kcJY5_SMCxFnzyKbgJFmH40md6yYoS7Xx1ROtp1y6vlzxpXIHIl21992ptpmbKFIUQ2ac71V63bq-3UHi9ZExGgRYaGuqzvpwxLl_JI98DrwVbNy3xezZL_j5iLn8Y9EB30GCDMlNPNY9z08uJfT-HS6ll0EgJQZ2B01VdnF0qd7AYQKTd_gxQ&expires_in=3600&token_type=Bearer",
                        "method": "GET",
                        "querystring": "",
                        "config": {
                            "distributionId": "EXAMPLE"
                        }
                    }
                }
            }
        ]
    }
    print(lambda_handler(event, None))
