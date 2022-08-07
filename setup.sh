

action=$1
somethingunique=$2

bucket=eu-${somethingunique}-s3-bucket-origin-public

stack_us_s3_bucket=us-${somethingunique}-s3-bucket
stack_us_cloudfront=us-${somethingunique}-cloudfront
stack_us_lambda_edge=us-${somethingunique}-lambda-edge
stack_us_userpool=us-${somethingunique}-userpool
stack_eu_apigw=eu-${somethingunique}-apigw
stack_eu_databasesetup=eu-${somethingunique}-databasesetup

startpwd=$(pwd)

check_lambda_exists() {
	fn=$1
	region=$2
	aws lambda get-function --function-name $fn --region $region > /dev/null 2>&1
	if [ $? -ne 0 ] ; then
		echo "Did not find $fn function"
		exit
	fi
}

create_vpc()
{
	aws cloudformation create-stack --stack-name eu-vpc-database-ec2 --template-body file://amazon-hellowebsql.yaml --capabilities CAPABILITY_NAMED_IAM --region eu-west-2
	./status.sh eu-vpc-database-ec2 eu-west-2
}

setup_lambda_to_createdb_tables() {
	cd $startpwd/dbsetuplambda

	echo "************** setup_lambda_to_createdb_tables ************************"
	sam build
	sam deploy --resolve-s3 --stack-name $stack_eu_databasesetup


	check_lambda_exists setupDatabaseTables eu-west-2
	
	aws lambda invoke --cli-binary-format raw-in-base64-out  --function-name setupDatabaseTables --payload '{  }'  out.json

}

setup_lambda_edge_and_cloudfront()
{
	cd $startpwd/lambda-edge
	echo "********************* setup_lambda_edge_and_cloudfront ********************"

	aws cloudformation create-stack --stack-name ${stack_us_s3_bucket} --template-body file://s3.yaml  --region us-east-1
	../status.sh ${stack_us_s3_bucket} us-east-1
	aws cloudformation create-stack --stack-name ${stack_us_cloudfront} --template-body file://cloudfront.yaml  --region us-east-1
	../status.sh ${stack_us_cloudfront} us-east-1
	
	aws cloudformation list-exports --region us-east-1 > out.json
	CloudFrontUrl=$(cat out.json |  jq -r '.Exports[]|select(.Name == "CloudFrontUrl")|.Value ')
	CloudFrontDistributionId=$(cat out.json |  jq -r '.Exports[]|select(.Name == "CloudFrontDistributionId")|.Value ')
	aws cloudformation create-stack --stack-name ${stack_us_userpool} --template-body file://userpool.yaml  --region us-east-1 --parameters ParameterKey=PoolName,ParameterValue=us-userpool ParameterKey=CallbackUrl,ParameterValue=$CloudFrontUrl
	
	../status.sh ${stack_us_userpool} us-east-1
	
	
	aws cloudformation list-exports --region us-east-1 > out.json
	userpool_id=$(cat out.json |  jq -r '.Exports[]|select(.Name == "us-userpool-UserPoolId")|.Value ')
	app_client_id=$(cat out.json |  jq -r '.Exports[]|select(.Name == "us-userpool-ClientId")|.Value ')
	user_pool_url=$(cat out.json |  jq -r '.Exports[]|select(.Name == "UserPoolUrl")|.Value ')
	
	sed -i -e "s/userpool_id =.*/userpool_id = '$userpool_id'/"  -e "s/app_client_id =.*/app_client_id = '$app_client_id='/" edge-us-east-1/decode-verify-jwt.py
	
	
	sam build
	sam deploy --region us-east-1 --resolve-s3 --stack-name $stack_us_lambda_edge
	
	aws cloudformation list-exports --region us-east-1 > out.json
	EdgeFunctionName=$(cat out.json |  jq -r '.Exports[]|select(.Name == "EdgeFunctionName")|.Value ')
	EdgeFunctionArn=$(cat out.json |  jq -r '.Exports[]|select(.Name == "EdgeFunctionArn")|.Value ')
	EdgeFunctionVersionArn="$EdgeFunctionArn:$(aws lambda list-aliases  --function-name  $EdgeFunctionName  --region us-east-1 | jq -r .Aliases[0].FunctionVersion)"
	PublicS3BucketName=$(cat out.json |  jq -r '.Exports[]|select(.Name == "PublicS3BucketName")|.Value ')
	PrivateS3BucketName=$(cat out.json |  jq -r '.Exports[]|select(.Name == "PrivateS3BucketName")|.Value ')

	
	check_lambda_exists $EdgeFunctionName us-east-1
	if [ -z "$userpool_id" -o -z "$CloudFrontUrl" -o -z "$PublicS3BucketName" -o -z "$PrivateS3BucketName" ] ; then
		echo "userpool_id=$userpool_id   CloudFrontUrl=$CloudFrontUrl   PublicS3BucketName=$PublicS3BucketName   PrivateS3BucketName=$PrivateS3BucketName"
		echo "Unexpected, did not find Cognito userpool ,Cloudfront url or s3 buckets"
		exit
	fi
}


setup_apigw()
{
	cd $startpwd/apigw
	echo "************************** setup_apigw *******************************"

	aws s3 mb s3://$bucket

	aws s3 cp swagger.json  s3://$bucket
	sam build
	sam deploy --region eu-west-2 --resolve-s3 --stack-name $stack_eu_apigw  --parameter-overrides \
		ParameterKey=appclientid,ParameterValue=$app_client_id \
		ParameterKey=userpoolid,ParameterValue=$userpool_id \
		ParameterKey=S3BucketName,ParameterValue=$bucket 

	aws cloudformation list-exports --region eu-west-2 > out.json

	apigwurl=$(cat out.json |  jq -r '.Exports[]|select(.Name == "AppApiEndpoint")|.Value ')

	if [ -z "$apigwurl" ] ; then
		echo "Did not find apigw url"
		exit
	fi

}

setup_html() {
	echo "********************************* setup_html *****************************"
	cd $startpwd/html

	sed -i -e "s|var UserPoolId =.*|var UserPoolId ='$userpool_id';|" -e "s|var ClientId =.*|var ClientId ='$app_client_id';|"  \
       		-e "s|var BaseURL =.*|var BaseURL = '$CloudFrontUrl';|"     \
       		-e "s|var Cognito =.*|var Cognito = '$user_pool_url';|"     \
       		-e "s|var apigwurl =.*|var apigwurl = '$apigwurl';|"     \
	index.html
	sed -i -e "s|var UserPoolId =.*|var UserPoolId ='$userpool_id';|" -e "s|var ClientId =.*|var ClientId ='$app_client_id';|"  \
       		-e "s|var BaseURL =.*|var BaseURL = '$CloudFrontUrl';|"     \
       		-e "s|var Cognito =.*|var Cognito = '$user_pool_url';|"     \
       		-e "s|var apigwurl =.*|var apigwurl = '$apigwurl';|"     \
	private/index.html

	aws s3 cp index.html s3://${PublicS3BucketName}
	aws s3 sync private s3://${PrivateS3BucketName}/private
}

update_cloudfront() {
	echo "********************************* update_cloudfront ********************************"
	cd $startpwd/lambda-edge

	aws cloudfront get-distribution-config --id $CloudFrontDistributionId --region us-east-1 > out.json
	Etag=`jq '.ETag' out.json | tr -d \"`

	lambda='{"Quantity": 1, "Items": [ { "LambdaFunctionARN": "'$EdgeFunctionVersionArn'", "EventType": "viewer-request", "IncludeBody": false } ] }'


	jq --argjson lambda "$lambda" '(.DistributionConfig.CacheBehaviors.Items[] | select(.PathPattern == "private/*").LambdaFunctionAssociations ) = $lambda ' out.json  | jq '.DistributionConfig' > out.json.updated


	aws cloudfront update-distribution --id $CloudFrontDistributionId  --region us-east-1 --distribution-config file://out.json.updated --if-match $Etag  > out.json


	aws cloudfront   list-distributions | jq -r '.DistributionList.Items[] | [ .Id, .Status]'
	
	sleep 5
	
	echo "Run this until it is ready"
	echo "aws cloudfront   list-distributions | jq -r '.DistributionList.Items[] | [ .Id, .Status]'"

	echo "visit    $CloudFrontUrl"

}


cleanup()
{
	cd $startpwd/lambda-edge
	aws cloudformation list-exports --region us-east-1 > out.json

	PublicS3BucketName=$(cat out.json |  jq -r '.Exports[]|select(.Name == "PublicS3BucketName")|.Value ')
	PrivateS3BucketName=$(cat out.json |  jq -r '.Exports[]|select(.Name == "PrivateS3BucketName")|.Value ')

	set -x	
	aws cloudformation delete-stack --stack-name ${stack_us_cloudfront} --region us-east-1
	aws cloudformation delete-stack --stack-name ${stack_eu_apigw} --region eu-west-2
	aws cloudformation delete-stack --stack-name ${stack_eu_databasesetup} --region eu-west-2

	aws cloudformation wait stack-delete-complete --stack-name ${stack_us_cloudfront} --region us-east-1
		
	aws cloudformation delete-stack --stack-name ${stack_us_lambda_edge} --region us-east-1
	aws cloudformation delete-stack --stack-name ${stack_us_userpool} --region us-east-1
	aws cloudformation delete-stack --stack-name ${stack_us_s3_bucket} --region us-east-1

	aws cloudformation wait stack-delete-complete --stack-name ${stack_us_userpool} --region us-east-1
	aws cloudformation wait stack-delete-complete --stack-name ${stack_us_s3_bucket} --region us-east-1
	aws cloudformation wait stack-delete-complete --stack-name ${stack_eu_apigw} --region eu-west-2
	aws cloudformation wait stack-delete-complete --stack-name ${stack_eu_databasesetup} --region eu-west-2
	aws cloudformation wait stack-delete-complete --stack-name ${stack_us_lambda_edge} --region us-east-1

	aws s3 rb --force s3://${PublicS3BucketName}
	aws s3 rb --force s3://${PrivateS3BucketName}
	aws s3 rb --force s3://$bucket

	set +x
}

if [ $action == "cleanup" ] ; then
	cleanup
	exit
fi
if [ $action == "create" -a "x$somethingunique" != "x"  ] ; then
	#pip3 install --user -r lambda-edge/edge-us-east-1/requirements.txt
	#pip3 install --user -r apigw/requirements.txt
	#pip3 install --user -r dbsetuplambda/lambda/requirements.txt
	pip install wheel


	setup_lambda_to_createdb_tables
	setup_lambda_edge_and_cloudfront
	setup_apigw
	setup_html
	update_cloudfront
	exit
fi
echo "either <cleanup or create>  and <phrase to add to items to create like hello123,batman,doorbell>"
exit 1
