GET {{website_url}}
HTTP 200
[Asserts]
header "Content-Type" exists
body contains "<title>crm</title>"
