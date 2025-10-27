locals {
  account_id = data.aws_caller_identity.current.account_id
  alarm_name = "crm-${var.region}-s3-objects-anomaly-detection"

  crm_infra_codebuild_project_down_name = "${var.crm_infra_project_name}-down"

  crm_infra_codebuild_project_down_source_configuration = {
    type      = "GITHUB"
    buildspec = "./aws/buildspecs/crm/down.yml"
    location  = "https://github.com/${var.source_repo_owner}/${var.source_repo_name}"
    depth     = 1
    version   = var.source_repo_branch
  }

  codebuild_rollback_source_configuration = {
    type      = "GITHUB"
    buildspec = "./aws/buildspecs/crm/release.yml"
    location  = "https://github.com/${var.source_repo_owner}/${var.source_repo_name}"
    depth     = 1
    version   = var.source_repo_branch
  }

  ubuntu_based_build = {
    builder_compute_type                = var.codebuild_environment.default_builder_compute_type
    builder_image                       = var.codebuild_environment.ubuntu_builder_image
    builder_type                        = var.codebuild_environment.default_builder_type
    builder_image_pull_credentials_type = var.codebuild_environment.default_builder_image_pull_credentials_type
    build_project_source                = var.codebuild_environment.default_build_project_source
    privileged_mode                     = true
  }

  amazonlinux2_based_build = {
    builder_compute_type                = var.codebuild_environment.default_builder_compute_type
    builder_image                       = var.codebuild_environment.amazonlinux2_builder_image
    builder_type                        = var.codebuild_environment.default_builder_type
    builder_image_pull_credentials_type = var.codebuild_environment.default_builder_image_pull_credentials_type
    build_project_source                = var.codebuild_environment.default_build_project_source
    privileged_mode                     = false
  }

  ecr_based_build = {
    builder_compute_type                = var.codebuild_environment.default_builder_compute_type
    builder_image                       = var.codebuild_environment.ecr_builder_image
    builder_type                        = var.codebuild_environment.default_builder_type
    builder_image_pull_credentials_type = var.codebuild_environment.default_builder_image_pull_credentials_type
    build_project_source                = var.codebuild_environment.default_build_project_source
    privileged_mode                     = true
  }
}

locals {
  crm_infra_build_projects = {
    validate = merge(local.amazonlinux2_based_build,
      { env_variables = {
        "ROLE_ARN"                           = module.crm_infra_codepipeline_iam_role.terraform_role_arn,
        "TF_VAR_SLACK_WORKSPACE_ID"          = var.SLACK_WORKSPACE_ID,
        "TF_VAR_CRM_ALERTS_SLACK_CHANNEL_ID" = var.CRM_ALERTS_SLACK_CHANNEL_ID,
        "TS_ENV"                             = var.environment,
        "AWS_DEFAULT_REGION"                 = var.region,
        "PYTHON_VERSION"                     = var.runtime_versions.python,
        "RUBY_VERSION"                       = var.runtime_versions.ruby,
        "GOLANG_VERSION"                     = var.runtime_versions.golang,
        "SCRIPT_DIR"                         = var.script_dir,
        }
      },
    { buildspec = "./aws/buildspecs/${var.crm_buildspecs}/validate.yml" })

    plan = merge(local.amazonlinux2_based_build,
      { env_variables = {
        "ROLE_ARN"                           = module.crm_infra_codepipeline_iam_role.terraform_role_arn,
        "TF_VAR_SLACK_WORKSPACE_ID"          = var.SLACK_WORKSPACE_ID,
        "TF_VAR_CRM_ALERTS_SLACK_CHANNEL_ID" = var.CRM_ALERTS_SLACK_CHANNEL_ID,
        "TS_ENV"                             = var.environment,
        "AWS_DEFAULT_REGION"                 = var.region,
        "RUBY_VERSION"                       = var.runtime_versions.ruby,
        "SCRIPT_DIR"                         = var.script_dir,
        }
      },
    { buildspec = "./aws/buildspecs/${var.crm_buildspecs}/plan.yml" })

    up = merge(local.amazonlinux2_based_build,
      { env_variables = {
        "ROLE_ARN"                           = module.crm_infra_codepipeline_iam_role.terraform_role_arn,
        "TF_VAR_SLACK_WORKSPACE_ID"          = var.SLACK_WORKSPACE_ID,
        "TF_VAR_CRM_ALERTS_SLACK_CHANNEL_ID" = var.CRM_ALERTS_SLACK_CHANNEL_ID,
        "TS_ENV"                             = var.environment,
        "AWS_DEFAULT_REGION"                 = var.region,
        "PYTHON_VERSION"                     = var.runtime_versions.python,
        "RUBY_VERSION"                       = var.runtime_versions.ruby,
        "SCRIPT_DIR"                         = var.script_dir,
        "CI_CD_CRM_PIPELINE_NAME"            = "${var.ci_cd_crm_project_name}-pipeline",
        "CLOUDFRONT_REGION"                  = var.cloudfront_configuration.region,
        }
      },
    { buildspec = "./aws/buildspecs/${var.crm_buildspecs}/up.yml" })
  }

  ci_cd_infra_build_projects = {
    validate = merge(local.amazonlinux2_based_build,
      { env_variables = {
        "ROLE_ARN"                             = module.ci_cd_infra_codepipeline_iam_role.terraform_role_arn,
        "TF_VAR_SLACK_WORKSPACE_ID"            = var.SLACK_WORKSPACE_ID,
        "TF_VAR_CODEPIPELINE_SLACK_CHANNEL_ID" = var.CODEPIPELINE_SLACK_CHANNEL_ID,
        "TF_VAR_REPORT_SLACK_CHANNEL_ID"       = var.REPORT_SLACK_CHANNEL_ID,
        "TF_VAR_CI_CD_ALERTS_SLACK_CHANNEL_ID" = var.CI_CD_ALERTS_SLACK_CHANNEL_ID,
        "TF_VAR_CRM_ALERTS_SLACK_CHANNEL_ID"   = var.CRM_ALERTS_SLACK_CHANNEL_ID,
        "TS_ENV"                               = var.environment,
        "AWS_DEFAULT_REGION"                   = var.region,
        "PYTHON_VERSION"                       = var.runtime_versions.python,
        "GOLANG_VERSION"                       = var.runtime_versions.golang,
        "RUBY_VERSION"                         = var.runtime_versions.ruby,
        "SCRIPT_DIR"                           = var.script_dir,
        }
      },
    { buildspec = "./aws/buildspecs/${var.ci_cd_infra_buildspecs}/validate.yml" })

    plan = merge(local.amazonlinux2_based_build,
      { env_variables = {
        "ROLE_ARN"                             = module.ci_cd_infra_codepipeline_iam_role.terraform_role_arn,
        "TF_VAR_SLACK_WORKSPACE_ID"            = var.SLACK_WORKSPACE_ID,
        "TF_VAR_CODEPIPELINE_SLACK_CHANNEL_ID" = var.CODEPIPELINE_SLACK_CHANNEL_ID,
        "TF_VAR_REPORT_SLACK_CHANNEL_ID"       = var.REPORT_SLACK_CHANNEL_ID,
        "TF_VAR_CI_CD_ALERTS_SLACK_CHANNEL_ID" = var.CI_CD_ALERTS_SLACK_CHANNEL_ID,
        "TF_VAR_CRM_ALERTS_SLACK_CHANNEL_ID"   = var.CRM_ALERTS_SLACK_CHANNEL_ID,
        "TS_ENV"                               = var.environment,
        "AWS_DEFAULT_REGION"                   = var.region,
        "PYTHON_VERSION"                       = var.runtime_versions.python,
        "RUBY_VERSION"                         = var.runtime_versions.ruby,
        "SCRIPT_DIR"                           = var.script_dir,
        "GITHUB_OWNER"                         = var.source_repo_owner,
        }
      },
    { buildspec = "./aws/buildspecs/${var.ci_cd_infra_buildspecs}/plan.yml" })

    up = merge(local.amazonlinux2_based_build,
      { env_variables = {
        "ROLE_ARN"                             = module.ci_cd_infra_codepipeline_iam_role.terraform_role_arn,
        "TF_VAR_SLACK_WORKSPACE_ID"            = var.SLACK_WORKSPACE_ID,
        "TF_VAR_REPORT_SLACK_CHANNEL_ID"       = var.REPORT_SLACK_CHANNEL_ID,
        "TF_VAR_CI_CD_ALERTS_SLACK_CHANNEL_ID" = var.CI_CD_ALERTS_SLACK_CHANNEL_ID,
        "TF_VAR_CRM_ALERTS_SLACK_CHANNEL_ID"   = var.CRM_ALERTS_SLACK_CHANNEL_ID,
        "TS_ENV"                               = var.environment,
        "AWS_DEFAULT_REGION"                   = var.region,
        "PYTHON_VERSION"                       = var.runtime_versions.python,
        "RUBY_VERSION"                         = var.runtime_versions.ruby,
        "SCRIPT_DIR"                           = var.script_dir,
        "GITHUB_OWNER"                         = var.source_repo_owner,
        }
      },
    { buildspec = "./aws/buildspecs/${var.ci_cd_infra_buildspecs}/up.yml" })
  }

  ci_cd_crm_build_projects = {
    batch_unit_mutation_lint = merge(local.ecr_based_build,
      { env_variables = {
        "CI"                        = 1
        "NODEJS_VERSION"            = var.runtime_versions.nodejs,
        "PYTHON_VERSION"            = var.runtime_versions.python,
        "PW_TEST_HTML_REPORT_OPEN"  = "never",
        "CRM_URL"                   = var.crm_url,
        "ENVIRONMENT"               = var.environment,
        "ACCOUNT_ID"                = local.account_id,
        "SCRIPT_DIR"                = var.script_dir,
        "TEST_REPORTS_BUCKET"       = module.test_reports_bucket.id,
        "CRM_GIT_REPOSITORY_BRANCH" = var.crm_repo_branch,
        "CRM_GIT_REPOSITORY_LINK"   = "https://github.com/${var.source_repo_owner}/${var.crm_content_repo_name}",
        }
      },
    { buildspec = "./aws/buildspecs/${var.crm_buildspecs}/batch_unit_mutation_integration_lint.yml" })

    deploy = merge(local.ubuntu_based_build,
      { env_variables = {
        "CI"                        = 1
        "NODEJS_VERSION"            = var.runtime_versions.nodejs,
        "PYTHON_VERSION"            = var.runtime_versions.python,
        "BUCKET_NAME"               = var.bucket_name,
        "SCRIPT_DIR"                = var.script_dir,
        "ALARM_NAME"                = local.alarm_name,
        "CRM_GIT_REPOSITORY_BRANCH" = var.crm_repo_branch,
        "CRM_GIT_REPOSITORY_LINK"   = "https://github.com/${var.source_repo_owner}/${var.crm_content_repo_name}",
        "CLOUDFRONT_REGION"         = var.cloudfront_configuration.region,
        "CLOUDFRONT_WEIGHT"         = var.continuous_deployment_policy_weight,
        "CLOUDFRONT_HEADER"         = var.continuous_deployment_policy_header,
        }
      },
    { buildspec = "./aws/buildspecs/${var.crm_buildspecs}/deploy.yml" })

    healthcheck = merge(local.amazonlinux2_based_build,
      { env_variables = {
        "CRM_URL" = var.crm_url
        }
      },
    { buildspec = "./aws/buildspecs/${var.crm_buildspecs}/healthcheck.yml" })

    batch_pw_load = merge(local.ecr_based_build,
      { env_variables = {
        "CI"                        = 1
        "NODEJS_VERSION"            = var.runtime_versions.nodejs,
        "PYTHON_VERSION"            = var.runtime_versions.python,
        "GOLANG_VERSION"            = var.runtime_versions.golang,
        "CRM_URL"                   = var.crm_url,
        "ENVIRONMENT"               = var.environment,
        "ACCOUNT_ID"                = local.account_id,
        "SCRIPT_DIR"                = var.script_dir,
        "PW_TEST_HTML_REPORT_OPEN"  = "never",
        "CLOUDFRONT_HEADER"         = var.continuous_deployment_policy_header,
        "LHCI_REPORTS_BUCKET"       = module.lhci_reports_bucket.id,
        "TEST_REPORTS_BUCKET"       = module.test_reports_bucket.id,
        "CRM_GIT_REPOSITORY_BRANCH" = var.crm_repo_branch,
        "CRM_GIT_REPOSITORY_LINK"   = "https://github.com/${var.source_repo_owner}/${var.crm_content_repo_name}",
        }
      },
    { buildspec = "./aws/buildspecs/${var.crm_buildspecs}/batch_pw_load.yml" })

    batch_lhci_leak = merge(local.ecr_based_build,
      { env_variables = {
        "CI"                        = 1
        "NODEJS_VERSION"            = var.runtime_versions.nodejs,
        "PYTHON_VERSION"            = var.runtime_versions.python,
        "CRM_URL"                   = var.crm_url,
        "ENVIRONMENT"               = var.environment,
        "ACCOUNT_ID"                = local.account_id,
        "SCRIPT_DIR"                = var.script_dir,
        "CLOUDFRONT_HEADER"         = var.continuous_deployment_policy_header,
        "LHCI_REPORTS_BUCKET"       = module.lhci_reports_bucket.id,
        "TEST_REPORTS_BUCKET"       = module.test_reports_bucket.id,
        "CRM_GIT_REPOSITORY_BRANCH" = var.crm_repo_branch,
        "CRM_GIT_REPOSITORY_LINK"   = "https://github.com/${var.source_repo_owner}/${var.crm_content_repo_name}",
        }
      },
    { buildspec = "./aws/buildspecs/${var.crm_buildspecs}/batch_lhci_leak.yml" })

    release = merge(local.ubuntu_based_build,
      { env_variables = {
        "PYTHON_VERSION"    = var.runtime_versions.python,
        "SCRIPT_DIR"        = var.script_dir,
        "CLOUDFRONT_REGION" = var.cloudfront_configuration.region,
        }
      },
    { buildspec = "./aws/buildspecs/${var.crm_buildspecs}/release.yml" })

  }

  crm_infra_build_project_down_env_variables = {
    "ROLE_ARN"                           = module.crm_infra_codepipeline_iam_role.terraform_role_arn,
    "TF_VAR_SLACK_WORKSPACE_ID"          = var.SLACK_WORKSPACE_ID,
    "TF_VAR_CRM_ALERTS_SLACK_CHANNEL_ID" = var.CRM_ALERTS_SLACK_CHANNEL_ID,
    "TS_ENV"                             = var.environment,
    "AWS_DEFAULT_REGION"                 = var.region,
    "RUBY_VERSION"                       = var.runtime_versions.ruby,
    "SCRIPT_DIR"                         = var.script_dir,
  }

  codebuild_cloudfront_rollback_project_env_variables = {
    "CLOUDFRONT_REGION" = var.cloudfront_configuration.region,
    "PYTHON_VERSION"    = var.runtime_versions.python,
    "SCRIPT_DIR"        = var.script_dir,
  }

  common_sandbox_env_variables = {
    "AWS_DEFAULT_REGION" = var.region,
    "PYTHON_VERSION"     = var.runtime_versions.python,
    "SCRIPT_DIR"         = var.script_dir,
    "PROJECT_NAME"       = var.sandbox_project_name,
    "GITHUB_REPOSITORY"  = "${var.source_repo_owner}/${var.crm_content_repo_name}",
  }

  sandbox_build_projects = {
    up = merge(local.amazonlinux2_based_build,
      {
        env_variables = merge(
          local.common_sandbox_env_variables,
          {
            "ROLE_ARN" = module.sandbox_codepipeline_iam_role.terraform_role_arn,
            "TS_ENV"   = var.environment,
          }
        )
      },
    { buildspec = "./aws/buildspecs/${var.sandbox_buildspecs}/up.yml" })

    deploy = merge(local.ecr_based_build,
      {
        env_variables = merge(
          local.common_sandbox_env_variables,
          {
            "CI"                      = "1",
            "NODEJS_VERSION"          = var.runtime_versions.nodejs,
            "BUCKET_NAME"             = var.bucket_name,
            "CRM_GIT_REPOSITORY_LINK" = "https://github.com/${var.source_repo_owner}/${var.crm_content_repo_name}",
          }
        )
      },
    { buildspec = "./aws/buildspecs/${var.sandbox_buildspecs}/deploy.yml" })

    healthcheck = merge(local.amazonlinux2_based_build,
      {
        env_variables = merge(
          local.common_sandbox_env_variables,
          {
            "BRANCH_NAME" = var.BRANCH_NAME,
          }
        )
      },
    { buildspec = "./aws/buildspecs/${var.sandbox_buildspecs}/healthcheck.yml" })
  }

  sandbox_delete_projects = {
    delete = merge(
      local.amazonlinux2_based_build,
      {
        project_name = "${var.project_name}-delete"
        env_variables = merge(
          local.common_sandbox_env_variables,
          {
            "BRANCH_NAME" = var.BRANCH_NAME,
          }
        )
      },
    { buildspec = "./aws/buildspecs/${var.sandbox_buildspecs}/delete.yml" })
  }
}