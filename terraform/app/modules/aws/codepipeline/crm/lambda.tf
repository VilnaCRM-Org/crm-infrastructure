resource "aws_iam_role" "iam_for_lambda" {
  name               = "${var.project_name}-iam-for-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_policy" "lambda_allow_sns_policy" {
  name        = "${var.project_name}-iam-policy-allow-sns-for-lambda"
  description = "A policy that allows send messages from Lambda to SNS"
  policy      = data.aws_iam_policy_document.lambda_allow_sns_policy.json
}

resource "aws_iam_role_policy_attachment" "lambda_allow_sns_policy_attachment" {
  role       = aws_iam_role.iam_for_lambda.name
  policy_arn = aws_iam_policy.lambda_allow_sns_policy.arn
}

resource "aws_iam_policy" "lambda_allow_logging_policy" {
  name        = "${var.project_name}-iam-policy-allow-logging-for-lambda"
  description = "A policy that allows send logs from Lambda to Cloudwatch"
  policy      = data.aws_iam_policy_document.lambda_allow_logging.json
}

resource "aws_iam_role_policy_attachment" "lambda_allow_logging_policy_attachment" {
  role       = aws_iam_role.iam_for_lambda.name
  policy_arn = aws_iam_policy.lambda_allow_logging_policy.arn
}

resource "aws_lambda_permission" "allow_codepipeline" {
  statement_id  = "AllowExecutionFromCodePipeline"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.func.arn
  principal     = "codepipeline.amazonaws.com"
  source_arn    = var.codepipeline_role_arn
}

resource "aws_lambda_permission" "allow_codebuild" {
  statement_id  = "AllowExecutionFromCodeBuild"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.func.arn
  principal     = "codebuild.amazonaws.com"
  source_arn    = var.codepipeline_role_arn
}

resource "aws_lambda_function" "func" {
  #checkov:skip=CKV_AWS_117:AWS VPC is not needed here for sending notifications
  #checkov:skip=CKV_AWS_50: X-Ray is not needed for such lambda and it takes bonus costs
  #checkov:skip=CKV_AWS_116: DLQ needs additional topics, to complex for simple redirect lambda function
  #checkov:skip=CKV_AWS_272: Code-signing is not needed for simple redirect lambda function
  #checkov:skip=CKV_AWS_173: KMS encryption is not needed
  #ts:skip=AWS.LambdaFunction.Logging.0472 AWS VPC is not needed here for sending notifications
  #ts:skip=AWS.LambdaFunction.Logging.0470 X-Ray is not needed for such lambda and it takes bonus costs
  filename                       = "${var.path_to_lambdas}/zip/reports_notification_function_payload.zip"
  function_name                  = local.lambda_reports_notifications_function_name
  role                           = aws_iam_role.iam_for_lambda.arn
  handler                        = "reports_notification.lambda_handler"
  runtime                        = var.lambda_python_version
  reserved_concurrent_executions = var.lambda_reserved_concurrent_executions

  logging_config {
    log_format = "JSON"
    log_group  = aws_cloudwatch_log_group.reports_notification_group.name
  }

  environment {
    variables = {
      SNS_TOPIC_ARN = "${aws_sns_topic.reports_notifications.arn}"
      ACCOUNT_ID    = "${local.account_id}"
    }
  }
  depends_on = [aws_cloudwatch_log_group.reports_notification_group]
}