import bpy
from typing import Final


POI_OBJECT_COLLECTION_NAME: Final[str] = "poi_object_collection"
POI_INSTANCE_COLLECTION_NAME: Final[str] = "poi_instance_collection"

def create_poi_geo_nodes(terrain: bpy.types.Object) -> bpy.types.Modifier:
    # Remove any old POI modifier
    if "poi_mod" in terrain.modifiers:
        terrain.modifiers.remove(terrain.modifiers["poi_mod"])
    
    # Create node group if it doesn't exist
    nodeGroup = bpy.data.node_groups.get("poi_geo_group")
    if not nodeGroup:
        nodeGroup = create_poi_node_group()

    geoMod = terrain.modifiers.new(name="poi_mod", type="NODES")
    geoMod.node_group = nodeGroup

    return geoMod
    

def create_poi_node_group() -> bpy.types.NodeGroup:
    print("Creating Node Group - Heavy Call!")

    # Defining the node group
    attributeName = "poi_index"
    nodeGroup = bpy.data.node_groups.new("poi_geo_group", "GeometryNodeTree")
    nodeGroup.interface.new_socket(name="Geometry", 
                                   in_out="OUTPUT", 
                                   socket_type="NodeSocketGeometry")
    
    nodes = nodeGroup.nodes
    links = nodeGroup.links
    outputNode = nodes.new("NodeGroupOutput")

    # Instance collection for the POI meshes to instance on
    instanceCollectionInfoNode = nodes.new("GeometryNodeCollectionInfo")
    instanceCollectionInfoNode.inputs["Collection"].default_value = bpy.data.collections.get(POI_INSTANCE_COLLECTION_NAME)
    instanceCollectionInfoNode.inputs["Separate Children"].default_value = True
    instanceCollectionInfoNode.inputs["Reset Children"].default_value = False  # Check this one
    instanceCollectionInfoNode.transform_space = "RELATIVE"

    # Storing the index as an attribute
    storeNamedAttributeNode = nodes.new("GeometryNodeStoreNamedAttribute")
    storeNamedAttributeNode.data_type = "INT"
    storeNamedAttributeNode.domain = "INSTANCE"
    storeNamedAttributeNode.inputs["Name"].default_value = attributeName

    # Generating and feeding in the index
    indexNode = nodes.new("GeometryNodeIndex")
    links.new(instanceCollectionInfoNode.outputs["Instances"], storeNamedAttributeNode.inputs["Geometry"])
    links.new(indexNode.outputs["Index"], storeNamedAttributeNode.inputs["Value"])

    # Realizing the instances to place on
    realizeInstancesNode = nodes.new("GeometryNodeRealizeInstances")
    links.new(storeNamedAttributeNode.outputs["Geometry"], realizeInstancesNode.inputs["Geometry"])

    # Creating the instancer node with the points to instance on
    instancer = nodes.new("GeometryNodeInstanceOnPoints")
    instancer.inputs["Pick Instance"].default_value = True
    links.new(realizeInstancesNode.outputs["Geometry"], instancer.inputs["Points"])

    # Creating an object collection for the models to instance
    objectCollectionInfoNode = nodes.new("GeometryNodeCollectionInfo")
    objectCollectionInfoNode.inputs["Collection"].default_value = bpy.data.collections.get(POI_OBJECT_COLLECTION_NAME)
    objectCollectionInfoNode.inputs["Separate Children"].default_value = True
    objectCollectionInfoNode.inputs["Reset Children"].default_value = True
    objectCollectionInfoNode.transform_space = "RELATIVE"
    links.new(objectCollectionInfoNode.outputs["Instances"], instancer.inputs["Instance"])

    # Feeding in the index to the instancer
    namedAttributeNode = nodes.new("GeometryNodeNamedAttribute")
    namedAttributeNode.data_type = "INT"
    namedAttributeNode.inputs["Name"].default_value = attributeName
    links.new(namedAttributeNode.outputs["Attribute"], instancer.inputs["Instance Index"])

    # Grabbing the output of the instancer
    links.new(instancer.outputs["Instances"], outputNode.inputs[0])

    return nodeGroup