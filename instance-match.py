import json


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
    instance_price["price_nuri_1yr_convertible"] = 0
    instance_price["price_nuri_3yr_standard"] = 0
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
    instance_price["is_arm"] = ("aws" in str(instance_price["product"]["attributes"]["physicalProcessor"]).lower())
    instance_price["is_intel"] = ("intel" in str(instance_price["product"]["attributes"]["physicalProcessor"]).lower())
    instance_price["is_amd"] = ("amd" in str(instance_price["product"]["attributes"]["physicalProcessor"]).lower())

    # Family
    instance_price["instance_family"] = str(instance_price["product"]["attributes"]["instanceType"]).split(".")[0]

    return instance_price

def get_price_ondemand(on_demand: dict) -> float:
    for _, item in on_demand.items():
        for _, price_dimension in item["priceDimensions"].items():
            price = float(price_dimension["pricePerUnit"]["USD"])
            return price
    print("ERROR - OnDemand price, please investigate!")

def remove_duplicate(seq: list, key: str) -> list:
    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x[key] in seen or seen_add(x[key]))]

def price_list_sorted(price_list: list[dict], key: str) -> list[dict]:
    only_valid_price = [ x for x in price_list if x[key] > 0 ]
    list_sorted = sorted(only_valid_price, key=lambda x: (x[key], x["id"]))
    # # Remove duplicate
    # list_sorted.reverse()
    # list_sorted = remove_duplicate(list_sorted, key)
    # list_sorted.reverse()
    return list_sorted

def normalize_price_list_from_json(price_list_json: dict, instance_types: dict) -> list[dict]:
    # Apparently price list is already sorted by family release
    price_to_remove = []
    price_list = []
    for index, x in enumerate(price_list_json["PriceList"]):
        # Add extra attibutes and convert current ones from string to proper value
        instance_price = convert_attributes(json.loads(x))
        instance_price["id"] = index

        # MUST be the last change before append, otherwise remove will fail later
        if instance_price["product"]["attributes"]["instanceType"] in instance_types:
            instance_price["describe"] = instance_types[instance_price["product"]["attributes"]["instanceType"]]
            instance_price["cores_value"] = int(instance_price["describe"]["VCpuInfo"]["DefaultCores"])
        else:
            # if it doesn't exist on describe, then it is not valid and it will be removed from price list
            price_to_remove.append(instance_price)
            # print(f'{instance_price["product"]["attributes"]["instanceType"]} not found')
        price_list.append(instance_price)

    # Remove invalid price
    for item in price_to_remove:
        price_list.remove(item)

    return price_list


def remove_duplicate_from_beginning(seq: list, key: str) -> list:
    seq.reverse()
    # print("--->>>>Before")
    # print_instance(seq)
    seq = remove_duplicate(seq, key)
    seq.reverse()
    # print("--->>>>After")
    # print_instance(seq)
    return seq

def get_lower_memory(memory: int) -> int:
    if memory <= 8:
        return memory
    elif memory <= 16:
        return memory - 4
    elif memory <= 64:
        return memory - 8
    else:
        return memory - 16

def print_instance(instances: list[dict]) -> None:
    for x in instances:
        print(f'{x["id"]:3} {x["product"]["attributes"]["instanceType"]:20} {x["vcpu_value"]:6} {x["memory_gigas"]:10}     {x["price_ondemand"]:<10} {x["price_reserved"]:<10}')

def get_instance(instances: list[dict], duplicate_key: str, memory: float, condition: callable) -> list[dict]:
    match_exactly = [ x for x in instances if x["memory_gigas"] == memory and condition(x) ]
    if match_exactly:
        #print("Exactly match")
        match_exactly = remove_duplicate_from_beginning(match_exactly, duplicate_key)
        return [match_exactly[0], match_exactly[0]]

    memory_lower = get_lower_memory(memory)
    match_lower_memory = [ x for x in instances if (x["memory_gigas"] >= memory_lower and x["memory_gigas"] <= memory) and condition(x) ]
    match_high_memory = [ x for x in instances if x["memory_gigas"] > memory and condition(x) ]

    if match_lower_memory and match_high_memory:
        match_lower_memory = remove_duplicate_from_beginning(match_lower_memory, duplicate_key)
        match_high_memory = remove_duplicate_from_beginning(match_high_memory, duplicate_key)

        # print_instance(match_lower_memory)
        # print("-----------")
        # print_instance(match_high_memory)
        # print("Match lower and high")

        return [match_lower_memory[0], match_high_memory[0]]
    elif match_lower_memory:
        match_lower_memory = remove_duplicate_from_beginning(match_lower_memory, duplicate_key)
        #print_instance(match_lower_memory)
        #print("Match lower")
        return [match_lower_memory[0], match_lower_memory[0]]
    elif match_high_memory:
        match_high_memory = remove_duplicate_from_beginning(match_high_memory, duplicate_key)
        #print_instance(match_high_memory)
        #print("Match high")
        return [match_high_memory[0], match_high_memory[0]]
    else:
        print("ERROR - This condition should never happens!!!")

def print_result(instances: list[dict], cpu_key: str) -> None:
    x = instances[0]
    y = instances[1]
    print(f'{x["product"]["attributes"]["instanceType"]:20} {x[cpu_key]:6} {x["memory_gigas"]:10}     {x["price_ondemand"]:<10} {x["price_reserved"]:<10}  |  {y["product"]["attributes"]["instanceType"]:20} {y[cpu_key]:6} {y["memory_gigas"]:10}     {y["price_ondemand"]:<10} {y["price_reserved"]:<10}')

def print_instance_recommendation(instances: list[dict], duplicate_key: str, cpu_key: str, memory: float, condition: callable) -> None:
    print_result(get_instance(instances, duplicate_key, memory, condition), cpu_key)

def main():
    # TODO: Read parameters from command line, including file names

    # Describe Instance Types from file
    with open("instance-types-us-east-1.json") as f:
        instance_types_json = json.load(f)

    instance_types={}
    for x in instance_types_json["InstanceTypes"]:
        key = x["InstanceType"]
        instance_types[key] = x

    # Price list from file
    with open("price-list-us-east-1.json") as f:
        price_list_json = json.load(f)

    # Apparently price list is already sorted by family release
    price_list = normalize_price_list_from_json(price_list_json, instance_types)

    # Sort price list by defined price
    on_demand_sorted = price_list_sorted(price_list, "price_ondemand")
    # price_reserved = Non Upfront Reserved Instance (3-year)
    reserved_sorted = price_list_sorted(price_list, "price_reserved")


    #################################################
    # TODO: Add main logic here
    with open("sparc.txt") as f:
        instances_to_match = f.readlines()

    for item in instances_to_match:
        parts = item.replace("\t", " ").strip().split(" ")
        memory = float(parts[0])
        cores = int(parts[3])
        print_instance_recommendation(on_demand_sorted, duplicate_key="price_ondemand", cpu_key="cores_value", memory=memory, condition=lambda x: x["cores_value"] >= cores and x["is_intel"])
        #print_instance_recommendation(reserved_sorted, duplicate_key="price_reserved", cpu_key="cores_value", memory=memory, condition=lambda x: x["cores_value"] >= cores and x["is_intel"])

    # print_result(get_instance(on_demand_sorted, duplicate_key="price_ondemand", memory=170, condition=lambda x: x["vcpu_value"] >= 4 and x["is_intel"]))
    #print_result(get_instance(on_demand_sorted, duplicate_key="price_ondemand", memory=260, condition=lambda x: x["describe"]["VCpuInfo"]["DefaultCores"] >= 14 and x["is_intel"]))
    # print("-------")
    # print_result(get_instance(reserved_sorted, duplicate_key="price_ondemand", memory=170, condition=lambda x: x["vcpu_value"] >= 4 and x["is_intel"]))
    # print_result(get_instance(reserved_sorted, duplicate_key="price_ondemand", memory=170, condition=lambda x: x["describe"]["VCpuInfo"]["DefaultCores"] >= 2 and x["is_intel"]))


    #print_instance(price_list)

    # filtered = [x for x in price_list if x["price_ondemand"] == 3.216 ]
    # print_instance(filtered)
    # print("------")
    # filtered = [x for x in on_demand_sorted if x["price_ondemand"] == 3.216 ]
    # print_instance(filtered)
    #print(json.dumps(filtered, indent=2))
    

    #for x in price_list:
        #print(x["product"]["attributes"].get("memory", "NotFound"), x["product"]["attributes"].get("memory_gigas", "NotFound"))
        #print(x["product"]["attributes"].get("memory", "NotFound"))
        #print(x["product"]["attributes"].get("memory_gigas", "NotFound"))
        #print(x["product"]["attributes"].get("clockSpeed", "NotFound"))
        #print(x["product"]["attributes"].get("instanceFamily", "NotFound"))
        #print(x["product"]["attributes"].get("instanceType", "NotFound"))
        #print(x.get("instance_family", "NotFound"))
        #print(x.get("price_ondemand", "NotFound"))


    # print(json.dumps(reserved[0], indent=2))





if __name__ == "__main__":
    main()