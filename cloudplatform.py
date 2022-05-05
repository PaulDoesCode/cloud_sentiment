# Cloud Platform Development
# cloudplatform.py
# by Paul Harbison-Smith (S1712745)

# imports
import boto3
import json
import time
import os
import cloudformationtemplate as cft

# declare variables
s3 = boto3.client("s3")
s3name = "phs-bucket-s1712745"
sqs = boto3.client("sqs")
sqsname = "phs-sqs-s1712745"
iam = boto3.client("iam")
lambdarolename = "phs-lambda-s1712745"
lambdaClient = boto3.client("lambda")

# create bucket
try:
    s3.create_bucket(Bucket = s3name, CreateBucketConfiguration = {"LocationConstraint":"eu-west-2"})
    print("S3 bucket created.")
except Exception as e:
    print(e)

# create SQS queue
# SQS queue also acts as trigger for Lambda
try:
    queue = sqs.create_queue(QueueName = sqsname, Attributes = {"DelaySeconds":"10"})
    print("SQS queue created")
except Exception as e:
    print(e) 

cft.createCloudFormationTemplateStack()

# gets the ARN for the queue 
# ARN is just a resource number which acts a unique identifier for the queue
# ARN is used later for configuring the bucket and the SQS queue
# ARN is used to configure the bucket and the queue policy (seen later)
sqsarn = sqs.get_queue_attributes(QueueUrl = queue["QueueUrl"], AttributeNames = ["QueueArn"])

# creates basic role policy document for the lambda function
# role policy document is used to give permissions to the lambda function, essentially
rolepolicydocument = {"Version":"2012-10-17","Statement":[{"Effect":"Allow", "Principal":{"Service":"lambda.amazonaws.com"}, "Action":"sts:AssumeRole"}]}

# creates the role for the lambda function using the role policy document 
try:
    iam.create_role(RoleName = lambdarolename, AssumeRolePolicyDocument = json.dumps(rolepolicydocument))
    print("Lambda role created.")
except Exception as e:
    print(e)

# adds required policies to the role
# without the policies you wouldn't be able to get a message from a queue, transcribe, read S3 data, etc.
iam.attach_role_policy(PolicyArn = "arn:aws:iam::aws:policy/service-role/AWSLambdaSQSQueueExecutionRole", RoleName = lambdarolename)
iam.attach_role_policy(PolicyArn = "arn:aws:iam::aws:policy/AmazonTranscribeFullAccess", RoleName = lambdarolename)
iam.attach_role_policy(PolicyArn = "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess", RoleName = lambdarolename)
iam.attach_role_policy(PolicyArn = "arn:aws:iam::aws:policy/ComprehendFullAccess", RoleName = lambdarolename)
iam.attach_role_policy(PolicyArn = "arn:aws:iam::aws:policy/AmazonSNSFullAccess", RoleName = lambdarolename)
iam.attach_role_policy(PolicyArn = "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess", RoleName = lambdarolename)

# code used to wait until the role creation has been completed
# otherwise couldn't assign roles to the lambda function since they will not have been created yet
# WHILE loop will loop until iamrole does not equal None, in which case the roles exist and the loop can finish
iamrole = None
time.sleep(10)
while True:
    iamrole = iam.get_role(RoleName = lambdarolename)
    if (iamrole != None):
        break
    time.sleep(3)
print("IAM roles assigned to Lambda.")

# open lambda function .zip file and read it
with open("lambda.zip", "rb") as F:
    lambdaZipCode = F.read()

# create lambda function using the .zip file and the created role
# initialise source mapping between the lambda function and the SQS 
# this means that when the SQS receives a message it triggers the lambda function 
# source mapping uses the ARN to identify which queue triggers the lambda function
try:
    lambdaFunction = lambdaClient.create_function(
        FunctionName = "phs-lambdafunction-s1712745",
        Runtime = "python3.8",
        Role = iamrole["Role"]["Arn"],
        Handler = "lambda.lambdahandler",
        Code = dict(ZipFile = lambdaZipCode),
        Timeout = 30,
        Environment = dict(Variables = dict())
    )
    lambdaClient.create_event_source_mapping(EventSourceArn = sqsarn["Attributes"]["QueueArn"], FunctionName = "phs-lambdafunction-s1712745", Enabled = True, BatchSize = 10)
    print("Lambda function created.")
except Exception as e:
    print(e)

# configures the bucket to send a message to the SQS when any object is inserted into the bucket
# uses the queue ARN to identify what queue to send a message to
BucketNotificationConfiguration = {
"QueueConfigurations":
    [{"Events":["s3:ObjectCreated:*"], 
    "Id":"Notifications", 
    "QueueArn":sqsarn["Attributes"]["QueueArn"]}]
}

# configures the SQS policy so that it can receive messages from the S3 bucket
# uses the queue ARN to identify what queue the queue policy should be attached to
QueuePolicy = {
    "Version": "2012-10-17",
    "Id":
        sqsarn["Attributes"]["QueueArn"],
    "Statement": [{
        "Sid": "allow bucket to notify SQS queue",
        "Effect": "Allow",
        "Principal": {"AWS": "*"},
        "Action": "SQS:SendMessage",
        "Resource": sqsarn["Attributes"]["QueueArn"],
        "Condition": {
            "ArnLike": {
                "aws:SourceArn": "arn:aws:s3:*:*:" + s3name
            }
        }
    }]
}

# "Policy" attributes needs to be JSON string rather than a dictionary
# use json.dumps to convert
QueueAttributes = {
    "Policy": json.dumps(QueuePolicy),
}

# set SQS attributes 
# QueueUrl used to identify which queue the attributes are being set for
sqs.set_queue_attributes(QueueUrl = queue["QueueUrl"], Attributes = QueueAttributes)

# sets up bucket so that it sends a message to SQS when an object is inserted
s3.put_bucket_notification_configuration(Bucket = s3name, NotificationConfiguration = BucketNotificationConfiguration)

# upload audio files in the folder
audioFolder = os.listdir("Audio/")

# FOR loop goes through the audio folder
# print file name
# upload file to S3 bucket
# time.sleep() so it uploads every 30 seconds
for file in audioFolder:
    print(file + " uploaded.")
    s3.upload_file("Audio/" + file, s3name, file)
    time.sleep(30)