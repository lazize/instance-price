import argparse
import json
import os

import boto3

# Instance Types
def describe_instance_types(region_name: str) -> dict:
    resp = {"InstanceTypes": []}
    client = boto3.client("ec2", region_name=region_name)
    paginator = client.get_paginator('describe_instance_types')
    response_iterator = paginator.paginate()
    for page in response_iterator:
        for instance_type in page["InstanceTypes"]:
            resp["InstanceTypes"].append(instance_type)
    return resp

def load_instance_types(region_name: str) -> dict:
    instance_types_file_name = f"instance-types-{region_name}.json"
    if not os.path.isfile(instance_types_file_name):
        with open(instance_types_file_name, "w") as f:
            describe = describe_instance_types(region_name)
            json.dump(describe, f, indent=4)

    # Describe Instance Types from file
    with open(instance_types_file_name) as f:
        instance_types_json = json.load(f)

    instance_types={}
    for x in instance_types_json["InstanceTypes"]:
        key = x["InstanceType"]
        instance_types[key] = x
    return instance_types


# Price list
def get_products(region_name: str, operating_system: str) -> dict:
    ###########################
    ## Operating System options
    ##########################
    # Linux
    # NA
    # RHEL
    # Red Hat Enterprise Linux with HA
    # SUSE
    # Ubuntu Pro
    # Windows

    # Must run in us-east-1
    client = boto3.client("pricing", region_name="us-east-1")
    paginator = client.get_paginator('get_products')
    response_iterator = paginator.paginate(
        ServiceCode="AmazonEC2",
        Filters=[
            { "Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used" },
            { "Type": "TERM_MATCH", "Field": "marketoption", "Value": "OnDemand" },
            { "Type": "TERM_MATCH", "Field": "regionCode", "Value": region_name },
            { "Type": "TERM_MATCH", "Field": "operatingSystem", "Value": operating_system },
            { "Type": "TERM_MATCH", "Field": "servicecode", "Value": "AmazonEC2" },
            { "Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared" },
            { "Type": "TERM_MATCH", "Field": "operation", "Value": "RunInstances" },
            { "Type": "TERM_MATCH", "Field": "currentGeneration","Value": "Yes" }
        ]
    )
    response = {
        "FormatVersion": "",
        "PriceList": [],
    }
    for page in response_iterator:
        response["FormatVersion"] = page["FormatVersion"]
        response["PriceList"] += page["PriceList"]
    return response

def load_price_list(region_name: str, operating_system: str) -> dict:
    price_list_file_name = f"price-list-{region_name}-{operating_system.lower().replace(" ", "")}.json"
    if not os.path.isfile(price_list_file_name):
        with open(price_list_file_name, "w") as f:
            describe = get_products(region_name, operating_system)
            json.dump(describe, f, indent=4)

    # Get price list from file
    with open(price_list_file_name) as f:
        price_list_json = json.load(f)

    instance_types = load_instance_types(region_name)
    price_list = normalize_price_list_from_json(price_list_json, instance_types)
    return price_list

def normalize_price_list_from_json(price_list_json: dict, instance_types: dict) -> list[dict]:
    # Apparently price list is already sorted by family release
    price_to_remove = []
    price_list = []
    for index, x in enumerate(price_list_json["PriceList"]):
        # MUST be the last change before append, otherwise remove will fail later
        instance_price = json.loads(x)
        
        if instance_price["product"]["attributes"]["instanceType"] in instance_types:
            instance_price["describe"] = instance_types[instance_price["product"]["attributes"]["instanceType"]]
            instance_price["cores_value"] = int(instance_price["describe"]["VCpuInfo"]["DefaultCores"])

            # Add extra attibutes and convert current ones from string to proper value
            instance_price = convert_attributes(instance_price)
            instance_price["id"] = index
        else:
            # if it doesn't exist on describe, then it is not valid and it will be removed from price list
            price_to_remove.append(instance_price)
        price_list.append(instance_price)

    # Remove invalid price.
    # The ones without describe instance types
    for item in price_to_remove:
        price_list.remove(item)

    return price_list

def convert_attributes(instance_price: dict) -> dict:
    # Memory
    memory = instance_price["product"]["attributes"]["memory"]
    memory_value = float(memory.split(" ")[0])
    instance_price["memory_gigas"] = memory_value

    # vCPU
    vcpu_value = int(instance_price["product"]["attributes"]["vcpu"])
    instance_price["vcpu_value"] = vcpu_value

    # Price
    instance_price["price_nuri_1yr_standard"] = 0
    instance_price["price_nuri_3yr_standard"] = 0
    instance_price["price_nuri_1yr_convertible"] = 0
    instance_price["price_nuri_3yr_convertible"] = 0

    for _, item in instance_price["terms"]["Reserved"].items():
        if str(item["termAttributes"]["PurchaseOption"]).lower().replace(" ", "") == "No Upfront".lower().replace(" ", ""):
            for _, price_dimension in item["priceDimensions"].items():
                price = float(price_dimension["pricePerUnit"]["USD"])
                key = f"price_nuri_{str(item['termAttributes']['LeaseContractLength']).lower().replace(" ", "")}_{str(item['termAttributes']['OfferingClass']).lower().replace(" ", "")}"
                instance_price[key] = price

    instance_price["price_ondemand"] = get_price_ondemand(instance_price["terms"]["OnDemand"])
    instance_price["price_reserved"] = instance_price["price_nuri_3yr_standard"]

    # Architecture
    instance_price["is_aws"] = ("aws" in str(instance_price["product"]["attributes"]["physicalProcessor"]).lower())
    instance_price["is_intel"] = ("intel" in str(instance_price["product"]["attributes"]["physicalProcessor"]).lower())
    instance_price["is_amd"] = ("amd" in str(instance_price["product"]["attributes"]["physicalProcessor"]).lower())

    # Family
    instance_price["instance_family"] = str(instance_price["product"]["attributes"]["instanceType"]).split(".")[0]
    
    # Type
    instance_price["instance_type"] = instance_price["product"]["attributes"]["instanceType"]

    # Processor Features
    instance_price["processor_features"] = []
    if "processorFeatures" in instance_price["product"]["attributes"]:
        instance_price["processor_features"] = [ x.strip().lower() for x in str(instance_price["product"]["attributes"]["processorFeatures"]).split(";") ]

    return instance_price

def get_price_ondemand(on_demand: dict) -> float:
    for _, item in on_demand.items():
        for _, price_dimension in item["priceDimensions"].items():
            price = float(price_dimension["pricePerUnit"]["USD"])
            return price
    print("ERROR - OnDemand price, please investigate!")


# Price list sorted
def price_list_sorted(price_list: list[dict], key: str) -> list[dict]:
    only_valid_price = [ x for x in price_list if key in x and x[key] > 0 ]
    list_sorted = sorted(only_valid_price, key=lambda x: (x[key], x["id"]))
    #list_sorted = sorted(only_valid_price, key=lambda x: x[key])
    return list_sorted


# Get Instance
def remove_duplicate(seq: list, key: str) -> list:
    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x[key] in seen or seen_add(x[key]))]

def remove_duplicate_from_beginning(seq: list, key: str) -> list:
    seq.reverse()
    seq = remove_duplicate(seq, key)
    seq.reverse()
    return seq

def get_lower_memory(memory_limits: list[tuple], memory: int) -> int:
    for limit in memory_limits:
        limit_size, limit_reduce = limit
        if memory >= limit_size:
            return memory - limit_reduce
    return memory

def get_lower_cpu(cpu_limits: list[tuple], cpu_value: int) -> int:
    for limit in cpu_limits:
        limit_size, limit_reduce = limit
        if cpu_value >= limit_size:
            return cpu_value - limit_reduce
    return cpu_value


def get_right_size_instance(price_list: list[dict], price_key: str, memory: float, cpu_key: str, cpu_value: int, args: any) -> list[dict]: # , memory_limits: list[tuple], cpu_limits: list[tuple]
    filtered = [ x for x in price_list if x["memory_gigas"] <= memory  ] # and x[cpu_key] <= cpu_value
    # Sort to get the max memory from filter before
    max_memory = max([x["memory_gigas"] for x in filtered])

    # Filter again to get only the ones with max memory
    filtered = [ x for x in filtered if x["memory_gigas"] == max_memory ]

    allow_reduce_cpu = args.allow_reduce_cpu
    if not allow_reduce_cpu:
        filtered = [ x for x in filtered if x[cpu_key] > cpu_value ]

    # Add proximity to cpu
    cpu_proximity_list = []
    for x in filtered:
        cpu_proximity = abs(cpu_value - x[cpu_key])
        x["cpu_proximity"] = cpu_proximity
        cpu_proximity_list.append(cpu_proximity)

    # Filter memory list to get the ones with min cpu proximity
    min_proximity = min(cpu_proximity_list)
    filtered = [ x for x in filtered if x["cpu_proximity"] == min_proximity ]

    # Sort to get the min price
    price_sorted = sorted(filtered, key=lambda x: (x[price_key], x["id"]))
    dedup = remove_duplicate_from_beginning(price_sorted, price_key)
    return dedup[0]

def get_direct_match_instance(price_list: list[dict], price_key: str, memory: float, cpu_key: str, cpu_value: int, args: any) -> list[dict]: # , memory_limits: list[tuple], cpu_limits: list[tuple]
    filtered = [ x for x in price_list if x["memory_gigas"] >= memory and x[cpu_key] >= cpu_value ]
    
    # Sort to get the min price
    price_sorted = sorted(filtered, key=lambda x: (x[price_key], x["id"]))
    dedup = remove_duplicate_from_beginning(price_sorted, price_key)
    return dedup[0]


def print_instance_recommendation(price_list: list[dict], instances_to_match: list[tuple], price_key: str, cpu_key: str, args: any) -> None: # , memory_limits: list[tuple], cpu_limits: list[tuple]
    recommendations = []
    for instance_to_match in instances_to_match:
        memory, cpu_value = instance_to_match
        right_size = get_right_size_instance(price_list, price_key, memory, cpu_key, cpu_value, args) # , memory_limits, cpu_limits
        direct_match = get_direct_match_instance(price_list, price_key, memory, cpu_key, cpu_value, args) # , memory_limits, cpu_limits
        recommendations.append((right_size, direct_match))

    output = args.output
    if output == "table":
        table_header = args.table_header
        if table_header:
            print(f'{"Instance Type":20} {"vCPU":6} {"Cores":6} {"Memory GiB":12}     {"USD":<10}', end="")
            print("  |  ", end="")
            print(f'{"Instance Type":20} {"vCPU":6} {"Cores":6} {"Memory GiB":12}     {"USD":<10}')
            print(f'{"-" * 20} {"-" * 6} {"-" * 6} {"-" * 12}     {"-" * 10}', end="")
            print("  |  ", end="")
            print(f'{"-" * 20} {"-" * 6} {"-" * 6} {"-" * 12}     {"-" * 10}')
        for recommendation in recommendations:
            x, y = recommendation
            print(f'{x["instance_type"]:20} {x["vcpu_value"]:6} {x["cores_value"]:6} {x["memory_gigas"]:12}     {x[price_key]:<10}', end="")
            print("  |  ", end="")
            print(f'{x["instance_type"]:20} {x["vcpu_value"]:6} {x["cores_value"]:6} {x["memory_gigas"]:12}     {x[price_key]:<10}')
    elif output == "json":
        print(json.dumps(recommendations, indent=2))
    else:
        print("ERROR - Invalid output option, please investigate!")


# List all
def print_instance(instances: list[dict], args: any) -> None:
    output = args.output
    if output == "table":
        table_header = args.table_header
        if table_header:
            print(f'{"Id":3}  {"Instance Type":20} {"vCPU":6} {"Cores":6} {"Memory GiB":12}     {"On-Demand":<15} {"NURI 3y Std":<15} {"NURI 1y Std":<15} {"NURI 3y Conv":<15} {"NURI 1y Conv":<15}')
            print(f'{"-" * 3}  {"-" * 20} {"-" * 6} {"-" * 6} {"-" * 12}     {"-" * 15} {"-" * 15} {"-" * 15} {"-" * 15} {"-" * 15}')
        for x in instances:
            print(f'{x["id"]:3}  {x["instance_type"]:20} {x["vcpu_value"]:6} {x["cores_value"]:6} {x["memory_gigas"]:12}     {x["price_ondemand"]:<15} {x["price_nuri_3yr_standard"]:<15} {x["price_nuri_1yr_standard"]:<15} {x["price_nuri_3yr_convertible"]:<15} {x["price_nuri_1yr_convertible"]:<15}')

    elif output == "json":
        print(json.dumps(instances, indent=2))
    else:
        print("ERROR - Invalid output option, please investigate!")


# Category
def get_instance_sorted_by_category(price_list: list[dict]) -> dict:
    categories = {}
    for x in price_list:
        # Inside price list instance category is called instanceFamily!
        instance_category = x["product"]["attributes"]["instanceFamily"]
        instance_type = x["instance_type"]
        if instance_category not in categories:
            categories[instance_category] = []
        categories[instance_category].append(instance_type)
    return categories

def print_instance_category(price_list: dict, args: any) -> None:
    categories = get_instance_sorted_by_category(price_list)

    category_output = args.category_output
    table_header = args.table_header

    if category_output == "short":
        for category in sorted(categories.keys()):
            instances = categories[category]
            print(f"{category}:")
            for x in instances:
                print(x, end=" ")
            print()
            print()
    elif category_output == "table":
        if table_header:
            print(f'{"Instance Category":40}  {"Instance Type":20} ')
            print(f'{"-" * 40}  {"-" * 20} ')
        for category in sorted(categories.keys()):
            for x in sorted(categories[category]):
                print(f'{category:40}  {x:20} ')
    else:
        print("ERROR - Invalid category output option, please investigate!")


# Attribute
def get_attribute_value_from_dict(object: dict, attributes: list) -> any:
    attribute = attributes[0]
    if attribute not in object:
        return "NotFound"

    if len(attributes) == 1:
        return object[attribute]
    return get_attribute_value_from_dict(object[attribute], attributes[1:])

def print_attribute(price_list: dict, args: any) -> None:
    attributes = args.attribute.split(".")
    for x in price_list:
        attribute_value = get_attribute_value_from_dict(x, attributes)
        print(attribute_value)


def main():
    operating_system_choices = ["Linux", "Windows", "RHEL", "SUSE", "Ubuntu Pro"]
    offering_class_choices = ["standard", "convertible"]
    lease_contract_length_choices = ["3yr", "1yr"]
    output_choices = ["table", "json"]
    category_output_choices = ["short", "table"]
    source_file_type_choices = ["csv", "tsv"]
    hypervisor_choices = ["nitro", "xen"]

    description ="""
    Get instance recommendation from AWS pricing.
    Show right-size and direct-match recommendations with the lowest price possible.

    For righ-size,
      Memory recommendation can be lower the one requested, but will be the most closer one.
      CPU recommendation can be lower the one requested, but will be the most closer one.
      If you don't want to reduce CPU, use --allow-reduce-cpu.

    For direct-match,
      CPU and Memory recommendation will always be equal or higher.

    Use only current instance types generation!
    """

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("region_name", help="AWS region to get pricing")

    group_price = parser.add_argument_group("Price", "Which price metric to use?")
    group_price.add_argument("--operating-system", help=f"AWS pricing for operating system system. Default: '{operating_system_choices[0]}'", choices=operating_system_choices, default=operating_system_choices[0])
    group_price_exclusive = group_price.add_mutually_exclusive_group()
    group_price_exclusive.add_argument("--on-demand", help="Best price for on-demand instance", default=False, action=argparse.BooleanOptionalAction)
    group_price_exclusive.add_argument("--reserved", help="Best price for reserved instance (only No Upfront)", default=False, action=argparse.BooleanOptionalAction)

    group_cpu = parser.add_argument_group("CPU Definition", "Which CPU metric should be use?")
    group_cpu_exclusive = group_cpu.add_mutually_exclusive_group()
    group_cpu_exclusive.add_argument("--vcpu", help="Number of vCPU's", default="", action=argparse.BooleanOptionalAction)
    group_cpu_exclusive.add_argument("--cores", help="Number of Cores", default="", action=argparse.BooleanOptionalAction)

    group_source = parser.add_argument_group("Source", "Source to get instance recommendation")
    group_source.add_argument("--file", help="Source File")
    group_source.add_argument("--file-type", help=f"Source file type. Default: '{source_file_type_choices[0]}'", choices=source_file_type_choices, default=source_file_type_choices[0])
    group_source.add_argument("--cpu-index", help="CPU index column from source file. Start at zero!")
    group_source.add_argument("--memory-index", help="Memory (in GiB) index column from source file. Start at zero!")
    group_source.add_argument("--allow-reduce-cpu", help="Allow reduce cpu on right-size recommendation", default=True, action=argparse.BooleanOptionalAction)
    # group_source.add_argument("--memory-limits", help="Tuple of memory size (in GiB) and lower limit accepted. Example: '260,16'. If source memory >= 260, accept instance type memory between 244 and 260", nargs="*")
    # group_source.add_argument("--cpu-limits", help="Tuple of cpu and lower limit accepted. Example: '48,10'. If source cpu >= 48, accept instance type cpu between 38 and 48", nargs="*")

    group_output = parser.add_argument_group("Output", "Output options")
    group_output.add_argument("--output", help=f"Output format. Default: '{output_choices[0]}'", choices=output_choices, default=output_choices[0])
    group_output.add_argument("--table-header", help="Show table header", default=True, action=argparse.BooleanOptionalAction)

    group_reserved = parser.add_argument_group("Reserved", "Get best price for reserved instance (only No Upfront). Cannot be used together with 'On-Demand'")
    group_reserved.add_argument("--offering-class", help=f"Offering class for reserved instance. Default: '{offering_class_choices[0]}'", choices=offering_class_choices, default=offering_class_choices[0])
    group_reserved.add_argument("--lease-contract-length", help=f"Length for reserved instance. Default: '{lease_contract_length_choices[0]}'", choices=lease_contract_length_choices, default=lease_contract_length_choices[0])

    group_filter = parser.add_argument_group("Filter", "Filter price list")
    group_filter.add_argument("--remove-category", help="Remove instance category from price list (not case sensitive)", nargs="*")
    group_filter.add_argument("--remove-family", help="Remove instance family from price list (not case sensitive)", nargs="*")
    group_filter.add_argument("--remove-type", help="Remove instance type from price list (not case sensitive)", nargs="*")
    group_filter.add_argument("--aws", help="AWS CPU", default=True, action=argparse.BooleanOptionalAction)
    group_filter.add_argument("--amd", help="AMD CPU", default=True, action=argparse.BooleanOptionalAction)
    group_filter.add_argument("--intel", help="Intel CPU", default=True, action=argparse.BooleanOptionalAction)
    group_filter.add_argument("--free-tier-eligible", help="Free Tier Eligible? If not set will consider all", default="", action=argparse.BooleanOptionalAction)
    group_filter.add_argument("--bare-metal", help="Bare Metal? If not set will consider all", default="", action=argparse.BooleanOptionalAction)
    group_filter.add_argument("--hypervisor", help="Which hypervisor to filter? If not set will consider all (not case sensitive)", choices=hypervisor_choices, nargs="*")
    group_filter.add_argument("--instance-storage-supported", help="Instance storage supported? If not set will consider all", default="", action=argparse.BooleanOptionalAction)
    group_filter.add_argument("--hibernation-supported", help="Hibernation supported? If not set will consider all", default="", action=argparse.BooleanOptionalAction)
    group_filter.add_argument("--burstable-performance-supported", help="Burstable performance supported? If not set will consider all", default="", action=argparse.BooleanOptionalAction)
    group_filter.add_argument("--dedicated-hosts-supported", help="Dedicated hosts supported? If not set will consider all", default="", action=argparse.BooleanOptionalAction)
    group_filter.add_argument("--auto-recovery-supported", help="Auto recovery supported? If not set will consider all", default="", action=argparse.BooleanOptionalAction)
    group_filter.add_argument("--processor-features", help="Processor features to filter? If not set will consider all (not case sensitive)", nargs="*")

    group_list_all = parser.add_argument_group("List All", "List all price/instance")
    group_output.add_argument("--list-all", help="List all instance types ordered by selected pricing", default=False, action=argparse.BooleanOptionalAction)

    group_category = parser.add_argument_group("List Category", "List instance type grouped by instance category")
    group_category.add_argument("--list-category", help="List all instance types grouped by instance category", default=False, action=argparse.BooleanOptionalAction)
    group_category.add_argument("--category-output", help=f"Output format for instance category. Default: '{category_output_choices[0]}'", choices=category_output_choices, default=category_output_choices[0])

    group_attribute = parser.add_argument_group("List Attribute", "List specific price or instance attribute")
    group_attribute.add_argument("--list-attribute", help="List specific price or instance attribute", default=False, action=argparse.BooleanOptionalAction)
    group_attribute.add_argument("--attribute", help="Attribute to list")

    args = parser.parse_args()

    # Validate parameters
    if args.list_attribute and not args.attribute:
        parser.error("Parameter 'attribute' must be set when use 'list-attribute'")
    if args.file:
        if not args.cpu_index:
            parser.error("Parameter 'cpu-index' must be set when use 'file'")
        if not args.memory_index:
            parser.error("Parameter 'memory-index' must be set when use 'file'")
        if not os.path.isfile(args.file):
            parser.error(f"File '{args.file}' not found")

    # memory_limits = []
    # if args.memory_limits:
    #     for memory_limit in args.memory_limits:
    #         if memory_limit:
    #             parts = memory_limit.split(",")
    #             if len(parts) != 2:
    #                 parser.error("Parameter 'memory-limits' must be a tuple of size 2")
    #             memory_limits.append((int(parts[0].strip()), int(parts[1].strip())))
    # memory_limits = sorted(memory_limits, key=lambda x: x[0], reverse=True)

    # cpu_limits = []
    # if args.cpu_limits:
    #     for cpu_limit in args.cpu_limits:
    #         if cpu_limit:
    #             parts = x.split(",")
    #             if len(parts) != 2:
    #                 parser.error("Parameter 'cpu-limits' must be a tuple of size 2")
    #             cpu_limits.append((int(parts[0].strip()), int(parts[1].strip())))
    # cpu_limits = sorted(cpu_limits, key=lambda x: x[0], reverse=True)

    # print("#####################################")
    # print(args)
    # print("#####################################")
    # return

    region_name = args.region_name
    operating_system = args.operating_system

    # Apparently price list is already sorted by family release
    price_list = load_price_list(region_name, operating_system)

    # Filter price list by defined arguments
    if not args.intel:
        price_list  = [ x for x in price_list if not x["is_intel"] ]
    if not args.amd:
        price_list  = [ x for x in price_list if not x["is_amd"] ]
    if not args.aws:
        price_list  = [ x for x in price_list if not x["is_aws"] ]
    if args.remove_category:
        remove_category = [ x.lower() for x in args.remove_category ]
        price_list  = [ x for x in price_list if str(x["product"]["attributes"]["instanceFamily"]).lower() not in remove_category ]
    if args.remove_family:
        remove_family = [ x.lower() for x in args.remove_family ]
        price_list  = [ x for x in price_list if str(x["instance_family"]).lower() not in remove_family ]
    if args.remove_type:
        remove_type = [ x.lower() for x in args.remove_type ]
        price_list  = [ x for x in price_list if str(x["instance_type"]).lower() not in remove_type ]
    if args.free_tier_eligible:
        price_list  = [ x for x in price_list if x["describe"]["FreeTierEligible"] == args.free_tier_eligible ]
    if args.bare_metal:
        price_list  = [ x for x in price_list if x["describe"]["BareMetal"] == args.bare_metal ]
    if args.hypervisor:
        hypervisor = [ x.lower() for x in args.hypervisor ]
        price_list  = [ x for x in price_list if str(x["describe"]["Hypervisor"]).lower() in hypervisor ]
    if args.instance_storage_supported:
        price_list  = [ x for x in price_list if x["describe"]["InstanceStorageSupported"] == args.instance_storage_supported ]
    if args.hibernation_supported:
        price_list  = [ x for x in price_list if x["describe"]["HibernationSupported"] == args.hibernation_supported ]
    if args.burstable_performance_supported:
        price_list  = [ x for x in price_list if x["describe"]["BurstablePerformanceSupported"] == args.burstable_performance_supported ]
    if args.dedicated_hosts_supported:
        price_list  = [ x for x in price_list if x["describe"]["DedicatedHostsSupported"] == args.dedicated_hosts_supported ]
    if args.auto_recovery_supported:
        price_list  = [ x for x in price_list if x["describe"]["AutoRecoverySupported"] == args.auto_recovery_supported ]
    if args.processor_features:
        processor_features = [ x.lower() for x in args.processor_features ]
        price_list = [x for x in price_list if all(feature in x["processor_features"] for feature in processor_features)]


    # List instance category
    # It doesn't require to sort the price list
    if args.list_category:
        print_instance_category(price_list, args)
        return

    # List specific price or instance attribute
    # It doesn't require to sort the price list
    if args.list_attribute:
        print_attribute(price_list, args)
        return


    # Everything down here requires to sort the price list
    if args.on_demand:
        selcted_price = "on-demand"
    elif args.reserved:
        selcted_price = f"{args.offering_class}-{args.lease_contract_length}"
    else:
        print("ERROR - Please select 'On-Demand' or 'Reserved'")
        return

    price_options = {
        "on-demand": "price_ondemand",
        "standard-1yr": "price_nuri_1yr_standard",
        "standard-3yr": "price_nuri_3yr_standard",
        "convertible-1yr": "price_nuri_1yr_convertible",
        "convertible-3yr": "price_nuri_3yr_convertible",
    }
    price_key = price_options[selcted_price]
    price_sorted = price_list_sorted(price_list, price_key)
    #print("Selected price", price_key)

    if args.list_all:
        print_instance(price_sorted, args)
        return

    # # Sort price list by defined price
    # on_demand_sorted = price_list_sorted(price_list, "price_ondemand")
    # # price_reserved = No Upfront Reserved Instance (3-year)
    # reserved_sorted = price_list_sorted(price_list, "price_reserved")


    #################################################
    if args.vcpu:
        cpu_key = "vcpu_value"
    elif args.cores:
        cpu_key = "cores_value"
    else:
        print("ERROR - Please select 'vcpu' or 'cores'")
        return

    with open(args.file) as f:
        source_lines = f.readlines()

    instances_to_match = []
    for line in source_lines:
        if args.file_type == "tsv":
            line = line.replace("\t", " ").strip()
        elif args.file_type == "csv":
            line = line.replace(",", " ").strip()
        else:
            print("ERROR - Invalid source file type. Please investigate!!!")
            return
        parts = line.split(" ")
        memory = float(parts[int(args.memory_index)])
        cpu_value = int(parts[int(args.cpu_index)])
        instances_to_match.append((memory, cpu_value))
    #instances_to_match = [(260,5)]
    print_instance_recommendation(price_sorted, instances_to_match, price_key=price_key, cpu_key=cpu_key, args=args) # , memory_limits=memory_limits, cpu_limits=cpu_limits

if __name__ == "__main__":
    main()