#!/bin/bash

stack=$1
region=$2
attempt=100
status=x

while [ $attempt -gt 0 -a $status != "ROLLBACK_FAILED" -a $(echo $status|grep -q COMPLETE; echo $?) -ne 0 ] ; do
        status=$(aws cloudformation describe-stacks --stack-name $stack --region $region | jq -r '.Stacks[0].StackStatus')
        echo $(date) [$status]
        let attempt=$attempt-1
        sleep 10
done
