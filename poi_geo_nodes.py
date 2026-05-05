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
    print("Creating POI Node Group - Heavy Call!")

    # Defining the node group
    attributeName = "poi_index"
    nodeGroup = bpy.data.node_groups.new("poi_geo_group", "GeometryNodeTree")

    # Defining I/O interfaces
    interface = nodeGroup.interface
    interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    nodes = nodeGroup.nodes
    links = nodeGroup.links
    inputNode = nodes.new("NodeGroupInput")
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
    indexNode = nodes.new("GeometryNodeInputIndex")
    links.new(instanceCollectionInfoNode.outputs["Instances"], storeNamedAttributeNode.inputs["Geometry"])
    links.new(indexNode.outputs["Index"], storeNamedAttributeNode.inputs["Value"])

    # Realizing the instances to place on
    realizeInstancesNode = nodes.new("GeometryNodeRealizeInstances")
    links.new(storeNamedAttributeNode.outputs["Geometry"], realizeInstancesNode.inputs["Geometry"])

    # Raycast node to get height for the points of interest
    raycastNode = nodes.new("GeometryNodeRaycast")
    raycastNode.inputs["Ray Direction"].default_value = (0, 0, -1)
    links.new(inputNode.outputs["Geometry"], raycastNode.inputs["Target Geometry"])

    # Set Position node to project every POI to its correct terrain height
    setPositionNode = nodes.new("GeometryNodeSetPosition")
    links.new(realizeInstancesNode.outputs["Geometry"], setPositionNode.inputs["Geometry"])
    links.new(raycastNode.outputs["Hit Position"], setPositionNode.inputs["Position"])
    links.new(raycastNode.outputs["Is Hit"], setPositionNode.inputs["Selection"])

    # Creating the instancer node with the points to instance on
    instancer = nodes.new("GeometryNodeInstanceOnPoints")
    instancer.inputs["Pick Instance"].default_value = True
    links.new(setPositionNode.outputs["Geometry"], instancer.inputs["Points"])

    # Creating an object collection for the models to instance
    objectCollectionInfoNode = nodes.new("GeometryNodeCollectionInfo")
    objectCollectionInfoNode.inputs["Collection"].default_value = bpy.data.collections.get(POI_OBJECT_COLLECTION_NAME)
    objectCollectionInfoNode.inputs["Separate Children"].default_value = True
    objectCollectionInfoNode.inputs["Reset Children"].default_value = True
    objectCollectionInfoNode.transform_space = "RELATIVE"
    links.new(objectCollectionInfoNode.outputs["Instances"], instancer.inputs["Instance"])

    # Feeding in the index to the instancer
    namedAttributeNode = nodes.new("GeometryNodeInputNamedAttribute")
    namedAttributeNode.data_type = "INT"
    namedAttributeNode.inputs["Name"].default_value = attributeName
    links.new(namedAttributeNode.outputs["Attribute"], instancer.inputs["Instance Index"])

    # Maybe ablation test the join geometry node, maybe we don't need to merge in terrain info
    # Adding in the join geometry node
    joinGeoNode = nodes.new("GeometryNodeJoinGeometry")
    links.new(inputNode.outputs["Geometry"], joinGeoNode.inputs["Geometry"])
    links.new(instancer.outputs["Instances"], joinGeoNode.inputs["Geometry"])

    # Returning the output of the instancer
    links.new(joinGeoNode.outputs["Geometry"], outputNode.inputs["Geometry"])

    return nodeGroup
