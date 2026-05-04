import bpy
import math
from typing import Final

MIN_TREE_SCALE: Final[float] = 0.95  # Relative scale variation
MAX_TREE_SCALE: Final[float] = 1.05  # Relative scale variation
TREE_COLLECTION_NAME: Final[str] = "tree_collection"


def create_tree_geo_nodes(terrain: bpy.types.Object, treeDensity: float) -> bpy.types.Modifier:
    # Create node group if it doesn't exist
    nodeGroup = bpy.data.node_groups.get("tree_geo_group")
    if not nodeGroup:
        nodeGroup = create_tree_node_group(treeDensity)

    geoMod = terrain.modifiers.new(name="tree_mod", type="NODES")
    geoMod.node_group = nodeGroup

    return geoMod
    

def create_tree_node_group(treeDensity: float) -> bpy.types.NodeGroup:
    print("Creating Node Group - Heavy Call!")
    # The trees should already be in the tree_collection, so grab them
    treeCollection = bpy.data.collections.get(TREE_COLLECTION_NAME)
    treeObjNames = [obj.name for obj in treeCollection.objects]
    
    if not treeObjNames:
        print("No trees to create node group!")
        return None

    nodeGroup = bpy.data.node_groups.new("tree_geo_group", "GeometryNodeTree")

    # Defining input interface
    interface = nodeGroup.interface
    interface.new_socket(
        name="terrain",
        in_out="INPUT",
        socket_type="NodeSocketGeometry",
    )

    # Defining output socket
    interface.new_socket(
        name="Geometry",
        in_out="OUTPUT",
        socket_type="NodeSocketGeometry",
    )

    nodes = nodeGroup.nodes
    links = nodeGroup.links

    # Creating input and output node groups
    groupInput = nodes.new("NodeGroupInput")
    groupOutput = nodes.new("NodeGroupOutput")

    # Creating inputs for the mask textures
    for i in range(len(treeObjNames)):
        interface.new_socket(
            name=f"mask_{i}",
            in_out="INPUT",
            socket_type="NodeSocketImage",
        )

    # Named Attribute Node for Terrain UV Map
    uvMapNode = nodes.new("GeometryNodeInputNamedAttribute")
    uvMapNode.inputs[0].default_value = "demUVmap"
    uvMapNode.data_type = "FLOAT_VECTOR"

    # Randomizes the scale of the trees for realism
    randomScale = nodes.new("FunctionNodeRandomValue")
    randomScale.data_type = "FLOAT_VECTOR"
    randomScale.inputs[0].default_value = [MIN_TREE_SCALE] * 3
    randomScale.inputs[1].default_value = [MAX_TREE_SCALE] * 3

    # Randomizes the rotation of the trees for realism
    randomRot = nodes.new("FunctionNodeRandomValue")
    randomRot.data_type = "FLOAT_VECTOR"
    randomRot.inputs[0].default_value = (0, 0, 0)  # Min rotation
    randomRot.inputs[1].default_value = (0, 0, 2 * math.pi)  # Max rotation

    # Create Object Collection Node for all trees
    collectionInfoNode = nodes.new("GeometryNodeCollectionInfo")
    collectionInfoNode.inputs["Collection"].default_value = bpy.data.collections.get(TREE_COLLECTION_NAME)
    collectionInfoNode.inputs["Separate Children"].default_value = True
    collectionInfoNode.inputs["Reset Children"].default_value = False
    collectionInfoNode.transform_space = "RELATIVE"

    # Creating Density and Identity Masks for Trees
    currentDensityOutput = None
    currentIdentityOutput = None
    for i in range(len(treeObjNames)):
        treeTexture = nodes.new("GeometryNodeImageTexture")
        treeTexture.interpolation = "Closest"
        treeTexture.extension = "CLIP"
        links.new(groupInput.outputs[f"mask_{i}"], treeTexture.inputs["Image"])
        links.new(uvMapNode.outputs["Attribute"], treeTexture.inputs["Vector"])

        tempDensityOutput = nodes.new("ShaderNodeMath")
        tempDensityOutput.operation = "ADD"
        links.new(treeTexture.outputs["Color"], tempDensityOutput.inputs[0])
        tempIdentityOutput = nodes.new("ShaderNodeMath")
        tempIdentityOutput.operation = "MULTIPLY"
        links.new(treeTexture.outputs["Color"], tempIdentityOutput.inputs[0])
        tempIdentityOutput.inputs[1].default_value = i

        if i == 0:
            tempDensityOutput.inputs[1].default_value = 0.0
        else:
            sumNode = nodes.new("ShaderNodeMath")
            sumNode.operation = "ADD"
            links.new(currentIdentityOutput.outputs["Value"], sumNode.inputs[0])
            links.new(tempIdentityOutput.outputs["Value"], sumNode.inputs[1])  # Identity Mask
            tempIdentityOutput = sumNode
            links.new(currentDensityOutput.outputs["Value"], tempDensityOutput.inputs[1])  # Density Mask
        
        currentIdentityOutput = tempIdentityOutput
        currentDensityOutput = tempDensityOutput
    
    # Adding a density scaler for the density mask
    densityScaler = nodes.new("ShaderNodeMath")
    densityScaler.operation = "MULTIPLY"
    densityScaler.inputs[0].default_value = treeDensity
    links.new(currentDensityOutput.outputs["Value"], densityScaler.inputs[1])

    # Adding in the distribute node
    distribute = nodes.new("GeometryNodeDistributePointsOnFaces")
    distribute.distribute_method = "RANDOM"
    links.new(densityScaler.outputs["Value"], distribute.inputs["Density"])
    links.new(groupInput.outputs["terrain"], distribute.inputs["Mesh"])

    # Adding in the instancer node for trees
    instancer = nodes.new("GeometryNodeInstanceOnPoints")
    instancer.inputs["Pick Instance"].default_value = True
    links.new(distribute.outputs["Points"], instancer.inputs["Points"])
    links.new(currentIdentityOutput.outputs["Value"], instancer.inputs["Instance Index"])
    links.new(collectionInfoNode.outputs["Instances"], instancer.inputs["Instance"])
    links.new(randomRot.outputs["Value"], instancer.inputs["Rotation"])
    links.new(randomScale.outputs["Value"], instancer.inputs["Scale"])

    # Adding in the join geometry node
    joinGeoNode = nodes.new("GeometryNodeJoinGeometry")
    links.new(groupInput.outputs["terrain"], joinGeoNode.inputs["Geometry"])
    links.new(instancer.outputs["Instances"], joinGeoNode.inputs["Geometry"])

    # Linking join node to output and setting terrain
    links.new(joinGeoNode.outputs[0], groupOutput.inputs[0])

    return nodeGroup