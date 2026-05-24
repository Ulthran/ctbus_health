output "webhook_url" {
  description = "Pass this to Telegram setWebhook"
  value       = "${aws_apigatewayv2_stage.default.invoke_url}/telegram"
}

output "health_data_bucket" {
  value = aws_s3_bucket.health_data.bucket
}

output "food_dlq_url" {
  value = aws_sqs_queue.food_dlq.url
}

output "frontend_url" {
  description = "Frontend URL"
  value       = "https://${var.domain_name}"
}

output "entry_api_url" {
  description = "Frontend entry submission endpoint"
  value       = "${aws_apigatewayv2_stage.entry.invoke_url}/entry"
}

output "cognito_hosted_ui_url" {
  description = "Cognito hosted UI base URL (used for login redirect)"
  value       = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${var.aws_region}.amazoncognito.com"
}

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  value       = aws_cognito_user_pool.main.id
}

output "cognito_client_id" {
  description = "Cognito App Client ID (needed for frontend auth flow)"
  value       = aws_cognito_user_pool_client.frontend.id
}
