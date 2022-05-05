# Cloud Platform Development
# lambda.py
# by Paul Harbison-Smith (S1712745)

# imports
import boto3
import json
import time
import urllib

# declare variables
transcribe = boto3.client("transcribe")
comprehend = boto3.client("comprehend")
sns = boto3.client("sns")
dynamo = boto3.resource("dynamodb", region_name = "eu-west-2")
databaseTable = dynamo.Table("phs-dbtable-s1712745")

# lambda function
def lambdahandler(event, context):
    try:
        # IF statement checks if the messages have data in them to ensure they aren't test messages
        # saves unnecessary work
        # IF statement then retrieves and extracts data from the event and assigns the relevant data to variables
        # data is then transcribed using the S3 URI to identify each file
        if "Records" in event:
            bucketObject = event["Records"][0]["body"]
            record = json.loads(bucketObject)
            bucketName = str(record["Records"][0]["s3"]["bucket"]["name"])
            fileName = str(record["Records"][0]["s3"]["object"]["key"])
            s3Uri = "s3://" + bucketName + "/" + fileName
            jobName = context.aws_request_id
            print(jobName)
            transcribe.start_transcription_job(
                TranscriptionJobName = jobName,
                Media = {"MediaFileUri": s3Uri}, MediaFormat = "mp3",
                LanguageCode = "en-US",
                Settings = {"ShowSpeakerLabels": True, "MaxSpeakerLabels": 2, "ChannelIdentification": False}
            )

            # WHILE loop loops until the transcription job status has either been set to "COMPLETED" or "FAILED"
            # print "Transcription in progress. Please wait." in CloudWatch logs until transcription job has completed or failed
            while True:
                status = transcribe.get_transcription_job(TranscriptionJobName = jobName)
                if status["TranscriptionJob"]["TranscriptionJobStatus"] in ["COMPLETED", "FAILED"]:
                    break
                print("Transcription in progress. Please wait.")
                time.sleep(2)

            # IF statement checks if the transcription job has been set to "COMPLETED"
            # sends transcription to comprehend which retrieves the sentiment data
            # urllib is used since transcribe returns a url containing data, use urllib to open the url
            if status["TranscriptionJob"]["TranscriptionJobStatus"] == "COMPLETED":
                response = urllib.request.urlopen(status["TranscriptionJob"]["Transcript"]["TranscriptFileUri"])
                transcriptFile = json.loads(response.read())
                transcription = transcriptFile["results"]["transcripts"][0]["transcript"]
                comprehendSentiment = comprehend.batch_detect_sentiment(TextList = [transcription], LanguageCode = "en")
                sentiment = comprehendSentiment["ResultList"][0]["Sentiment"]

            # print audio file name + file sentiment data in CloudWatch logs for lambda
            print("File: " + fileName + " " + "Sentiment: " + sentiment)

            # sentiment data is stored in the DynamoDB database
            databaseTable.put_item(Item = {"File":fileName, "FileSentiment":sentiment})

            # IF statement checks if the sentiment for a given audio file entry is negative
            # if the sentiment is negative, send an SMS message to a given number
            if sentiment == "NEGATIVE":
                sns.publish(PhoneNumber = "[PUT PHONE NUMBER HERE]", Message = sentiment)
                return True
        return False
    except Exception as e:
        print(e)
        return False