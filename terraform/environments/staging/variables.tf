variable "aws_account_id" {
  type    = string
  default = "682033461796"
}

variable "image_tag" {
  description = "Tag of the openforge_catalog/api image to run (the git sha the Staging workflow pushed)"
  type        = string
}
