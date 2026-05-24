locals {
  s3_base_url   = "https://${var.domain_name}"
  entry_api_url = "${aws_apigatewayv2_stage.entry.invoke_url}/entry"

  index_html_content = replace(
    replace(
      replace(
        replace(
          file("${path.module}/../frontend/index.html"),
          "CTBUS_S3_PLACEHOLDER",
          local.s3_base_url
        ),
        "CTBUS_API_PLACEHOLDER",
        local.entry_api_url
      ),
      "CTBUS_COGNITO_DOMAIN_PLACEHOLDER",
      "${aws_cognito_user_pool_domain.main.domain}.auth.${var.aws_region}.amazoncognito.com"
    ),
    "CTBUS_CLIENT_ID_PLACEHOLDER",
    aws_cognito_user_pool_client.frontend.id
  )

  frontend_src_files = {
    "src/main.js"             = { path = "${path.module}/../frontend/src/main.js",             content_type = "application/javascript" }
    "src/auth.js"             = { path = "${path.module}/../frontend/src/auth.js",             content_type = "application/javascript" }
    "src/App.vue"             = { path = "${path.module}/../frontend/src/App.vue",             content_type = "text/plain" }
    "src/views/Dashboard.vue" = { path = "${path.module}/../frontend/src/views/Dashboard.vue", content_type = "text/plain" }
    "src/views/Week.vue"      = { path = "${path.module}/../frontend/src/views/Week.vue",      content_type = "text/plain" }
    "src/views/Month.vue"     = { path = "${path.module}/../frontend/src/views/Month.vue",     content_type = "text/plain" }
    "src/views/Entry.vue"     = { path = "${path.module}/../frontend/src/views/Entry.vue",     content_type = "text/plain" }
    "src/views/Recipes.vue"   = { path = "${path.module}/../frontend/src/views/Recipes.vue",   content_type = "text/plain" }
    "src/views/Usage.vue"     = { path = "${path.module}/../frontend/src/views/Usage.vue",     content_type = "text/plain" }
  }
}

resource "aws_s3_object" "frontend_index" {
  bucket        = aws_s3_bucket.health_data.id
  key           = "index.html"
  content       = local.index_html_content
  content_type  = "text/html"
  cache_control = "no-cache"
  etag          = md5(local.index_html_content)
}

resource "aws_s3_object" "frontend_src" {
  for_each      = local.frontend_src_files
  bucket        = aws_s3_bucket.health_data.id
  key           = each.key
  source        = each.value.path
  content_type  = each.value.content_type
  cache_control = "no-cache"
  etag          = filemd5(each.value.path)
}
