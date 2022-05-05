# Cloud Platform Development
# cloudformationtemplate.py
# by Paul Harbison-Smith (S1712745)

# imports
import boto3
import json

# declare variables
cloudFormation = boto3.client("cloudformation")

# imports DynamoDB template json file as a dictionary
# cloud formation then used to create stack which creates a DynamoDB table
# json.dumps turns dictionary into a JSON string since the template body requires a JSON string rather than a dictionary
def createCloudFormationTemplateStack():
    with open("database.json") as databaseTemplate:
        cloudFormationTemplate = json.load(databaseTemplate)
    try:
        cloudFormation.create_stack(StackName = "phs-cftemplatestack-s1712745", TemplateBody = json.dumps(cloudFormationTemplate))
        print("DynamoDB database created.")
    except Exception as e:
        print(e)
        return True