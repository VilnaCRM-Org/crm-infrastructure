#!/bin/bash
# shellcheck disable=SC2148
chmod +x ~
chown -R codebuild-user:codebuild-user /codebuild-user/crm
chown -R codebuild-user:codebuild-user "$CODEBUILD_SRC_DIR"
chown -R codebuild-user:codebuild-user /usr/local/lib/node_modules/
