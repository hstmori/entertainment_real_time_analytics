data "oci_core_services" "regional" {
  count = local.create_network ? 1 : 0
}

locals {
  oracle_services_network = try(
    [
      for service in data.oci_core_services.regional[0].services : service
      if can(regex("^All .* Services", service.name))
    ][0],
    null,
  )
}

resource "oci_core_vcn" "lakehouse" {
  count = local.create_network ? 1 : 0

  cidr_blocks    = [var.vcn_cidr]
  compartment_id = var.compartment_ocid
  display_name   = "${local.name_prefix}-vcn"
  dns_label      = "entlake"
  freeform_tags  = local.common_tags
}

resource "oci_core_nat_gateway" "lakehouse" {
  count = local.create_network ? 1 : 0

  compartment_id = var.compartment_ocid
  display_name   = "${local.name_prefix}-nat"
  freeform_tags  = local.common_tags
  vcn_id         = oci_core_vcn.lakehouse[0].id
}

resource "oci_core_service_gateway" "lakehouse" {
  count = local.create_network ? 1 : 0

  compartment_id = var.compartment_ocid
  display_name   = "${local.name_prefix}-service-gateway"
  freeform_tags  = local.common_tags
  vcn_id         = oci_core_vcn.lakehouse[0].id

  services {
    service_id = local.oracle_services_network.id
  }
}

resource "oci_core_route_table" "private" {
  count = local.create_network ? 1 : 0

  compartment_id = var.compartment_ocid
  display_name   = "${local.name_prefix}-private-routes"
  freeform_tags  = local.common_tags
  vcn_id         = oci_core_vcn.lakehouse[0].id

  route_rules {
    description       = "Outbound access for package and image retrieval"
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_nat_gateway.lakehouse[0].id
  }

  route_rules {
    description       = "Private access to Object Storage and OCI services"
    destination       = local.oracle_services_network.cidr_block
    destination_type  = "SERVICE_CIDR_BLOCK"
    network_entity_id = oci_core_service_gateway.lakehouse[0].id
  }
}

resource "oci_core_security_list" "private" {
  count = local.create_network ? 1 : 0

  compartment_id = var.compartment_ocid
  display_name   = "${local.name_prefix}-private-security"
  freeform_tags  = local.common_tags
  vcn_id         = oci_core_vcn.lakehouse[0].id

  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
  }

  ingress_security_rules {
    description = "Kafka TLS listeners from the lakehouse VCN"
    protocol    = "6"
    source      = var.vcn_cidr

    tcp_options {
      max = 9093
      min = 9092
    }
  }

  ingress_security_rules {
    description = "Oracle SQL Net TLS from the lakehouse VCN"
    protocol    = "6"
    source      = var.vcn_cidr

    tcp_options {
      max = 1522
      min = 1521
    }
  }
}

resource "oci_core_subnet" "private" {
  count = local.create_network ? 1 : 0

  cidr_block                 = var.private_subnet_cidr
  compartment_id             = var.compartment_ocid
  display_name               = "${local.name_prefix}-private-subnet"
  dns_label                  = "private"
  freeform_tags              = local.common_tags
  prohibit_internet_ingress  = true
  prohibit_public_ip_on_vnic = true
  route_table_id             = oci_core_route_table.private[0].id
  security_list_ids          = [oci_core_security_list.private[0].id]
  vcn_id                     = oci_core_vcn.lakehouse[0].id
}
