# aws-hellowebsql, note AWS costs apply

![Alt text](docs/overview.drawio.png?raw=true)

**There will be a cost if you provision this!!**

This project will create a serverless https website what uses Cognito for authentication.
Once authenticated you can access the private html and call 2 api's that read and update a database

us-east-1 (must be here for Cloudfront)
Cloudfront offers https website with html on s3. 
Public webpage has Cognito link for authentication 
Cloudfront uses a lambda to check jwt using a lambda@edge before allowing access to private html

The APIGW has 2 resources that front end an RDS database in a private subnet
The APIGW uses 1 Lambda to verify the token against Cognito userpool
The APIGW uses another Lambda to run code to access the private database

The AWS configuration has an ec2 instance simply to offer an easy way to run the setup script.

# how to setup

[![Youtube demo video](http://img.youtube.com/vi/dNQDL11115A/0.jpg)](http://www.youtube.com/watch?v=dNQDL11115A "Youtube Video Demo")

As an administrator log onto AWS console in eu-west-2

Go to Cloudformation and create a new stack. You can accept all the defaults. This will create
VPC,Subnets,RDS and EC2 instance. 

Have not used a custom resource in Cloudformation to create db schema, that's a separate Lambda created below.

Log onto the EC2 instance using session manager. The EC2 is in a private subnet, you will be logged
in as
uid=1001(ssm-user) gid=1001(ssm-user) groups=1001(ssm-user)
```commandline
cd $HOME
git clone https://github.com/bernardjason/aws-hellowebsql.git
cd aws-hellowebsql
bash setup create <random name, has to be something unique like as used for resources> 
#After about 10-15 minutes script will end. To check state of Cloudfron update
aws cloudfront   list-distributions | jq -r '.DistributionList.Items[] | [ .Id, .Status]'
```
wait until deploy complete then visit site.

# to cleanup
```commandline
cd $HOME/aws-hellowebsql
bash setup cleanup <same name as create>
```

# with thanks.
https://aws.amazon.com/blogs/networking-and-content-delivery/authorizationedge-using-cookies-protect-your-amazon-cloudfront-content-from-being-downloaded-by-unauthenticated-users/

https://github.com/awslabs/aws-support-tools/blob/master/Cognito/decode-verify-jwt/decode-verify-jwt.py
