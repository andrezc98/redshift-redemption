variable "alert_email" {
  type        = string
  description = "Budget alert recipient"
}

variable "ra3_enabled" {
  type    = bool
  default = false
}

variable "rg_snapshot_id" {
  type        = string
  default     = ""
  description = "Manual snapshot of rr-ra3 to restore rr-rg from; empty = no RG cluster"
}

variable "serverless_enabled" {
  type    = bool
  default = false
}

variable "serverless_rpu" {
  type        = number
  default     = 4
  description = "Base and max RPU of the Serverless workgroup (4, or multiples of 8 up to 512)"
}
