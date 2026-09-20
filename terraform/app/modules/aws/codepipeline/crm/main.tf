resource "aws_codepipeline" "terraform_pipeline" {
  #checkov:skip=CKV_AWS_219: S3 bucket has encryption by default
  name           = "${var.project_name}-pipeline"
  role_arn       = var.codepipeline_role_arn
  tags           = var.tags
  pipeline_type  = "V2"
  execution_mode = "QUEUED"

  artifact_store {
    location = var.s3_bucket_name
    type     = "S3"
  }

  stage {
    name = "Source"

    action {
      name             = "Download-Source"
      category         = "Source"
      owner            = "AWS"
      provider         = "CodeStarSourceConnection"
      version          = "1"
      namespace        = "SourceVariables"
      output_artifacts = ["SourceOutput"]
      run_order        = 1

      configuration = {
        ConnectionArn    = var.codestar_connection_arn
        FullRepositoryId = "${var.source_repo_owner}/${var.source_repo_name}"
        BranchName       = var.source_repo_branch
        DetectChanges    = var.detect_changes
      }
    }

    action {
      name             = "CrmSource"
      category         = "Source"
      owner            = "AWS"
      provider         = "CodeStarSourceConnection"
      version          = "1"
      namespace        = "CrmSourceVariables"
      output_artifacts = ["CrmSource"]
      run_order        = 1

      configuration = {
        ConnectionArn    = var.codestar_connection_arn
        FullRepositoryId = "${var.source_repo_owner}/${var.crm_content_repo_name}"
        BranchName       = var.crm_repo_branch
        DetectChanges    = "true"
      }
    }
  }

  dynamic "stage" {
    # QUEUED locks each stage, not the whole pipeline. Keep every action that
    # deploys, checks, or promotes shared staging content under the same lock.
    for_each = [
      {
        name    = "Stage-batch-unit-mutation-lint"
        actions = slice(var.stages, 0, 1)
      },
      {
        name    = "Stage-deployment"
        actions = slice(var.stages, 1, length(var.stages))
      }
    ]

    content {
      name = stage.value.name
      dynamic "action" {
        for_each = stage.value.actions

        content {
          category         = action.value.category
          name             = "Action-${action.value.name}"
          owner            = action.value.owner
          provider         = action.value.provider
          input_artifacts  = action.value.input_artifacts
          output_artifacts = [action.value.output_artifacts]
          version          = "1"
          run_order        = action.key + 1

          configuration = {
            CombineArtifacts = startswith(action.value.name, "batch") ? true : false
            BatchEnabled     = startswith(action.value.name, "batch") ? true : false
            ProjectName      = action.value.provider == "CodeBuild" ? "${var.project_name}-${action.value.name}" : null
            PrimarySource    = action.value.provider == "CodeBuild" && length(action.value.input_artifacts) > 1 ? action.value.input_artifacts[0] : null
            EnvironmentVariables = action.value.provider == "CodeBuild" ? jsonencode([
              {
                name  = "CRM_SOURCE_VERSION"
                value = "#{CrmSourceVariables.CommitId}"
                type  = "PLAINTEXT"
              }
            ]) : null
          }
        }
      }
    }
  }
}

resource "aws_codestarnotifications_notification_rule" "codepipeline_rule" {
  detail_type = "BASIC"
  event_type_ids = [
    "codepipeline-pipeline-pipeline-execution-failed",
    "codepipeline-pipeline-pipeline-execution-canceled",
    "codepipeline-pipeline-pipeline-execution-started",
    "codepipeline-pipeline-pipeline-execution-resumed",
    "codepipeline-pipeline-pipeline-execution-succeeded",
    "codepipeline-pipeline-pipeline-execution-superseded",
  ]

  name     = "${var.project_name}-notifications"
  resource = aws_codepipeline.terraform_pipeline.arn

  target {
    address = aws_sns_topic.codepipeline_notifications.arn
  }

  tags = var.tags
}
