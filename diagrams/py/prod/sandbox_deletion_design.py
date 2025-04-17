from diagrams import Cluster, Diagram
from diagrams.onprem.vcs import Github
from diagrams.aws.devtools import Codebuild
from diagrams.aws.integration import Eventbridge
from diagrams.aws.compute import LambdaFunction
from diagrams.aws.storage import SimpleStorageServiceS3

with Diagram(
    "\nSandbox Deletion Flow Design - VilnaCRM",
    show=False,
    filename="../../img/prod/sandbox_deletion_design",
):
    gh = Github("Github Repository")
    codebuild_deploy = Codebuild("AWS CodeBuild \n deploy")

    with Cluster("Deletion Trigger Setup"):
        rule = Eventbridge("EventBridge Rule \n (delay 7 days)")
        lambda_fn = LambdaFunction("Lambda Function \n Delete Sandbox")
        s3 = SimpleStorageServiceS3("S3 Sandbox Bucket")

    gh >> codebuild_deploy

    # deploy stage sets up rule
    codebuild_deploy >> rule

    # rule triggers lambda
    rule >> lambda_fn

    # lambda deletes bucket and itself
    lambda_fn >> s3
    lambda_fn >> rule
