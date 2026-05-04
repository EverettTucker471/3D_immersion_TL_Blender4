"""
@description: Implements a minimial version of Modeling 3D optimized
for use with Blender 5.0.1

Respects:
camelCase for variables
snake_case for functions

@date 1/21/2026
@author(s): Everett Tucker
"""

import os
import math
import bpy
import bmesh
from .settings import getSettings
from bpy.props import StringProperty
from mathutils import Vector
from typing import Final, Tuple, Dict, List
from tree_geo_nodes import create_tree_geo_nodes
from poi_geo_nodes import create_poi_geo_nodes

# Static File Paths
WATCH_NAME: Final[str] = "Watch"
TERRAIN_FILE: Final[str] = "terrain.tif"
WATER_FILE: Final[str] = "water.tif"
WATER_OBJECT: Final[str] = "water"
TERRAIN_OBJECT: Final[str] = "terrain"
TEXTURE_PATH: Final[str] = "texture.tif"
VIEW_INCREASE_FACTOR: Final[int] = 5
SUN_INCREASE_FACTOR: Final[int] = 2
TEXTURE_MAPPING_SCALE: Final[int] = 3
TERRAIN_ROUGHNESS: Final[float] = 0.8
SLOPE_LIMIT: Final[float] = 0.4  # Limit for defining what counts as a side

# Initial Parameters for the Sun
SUN_ENERGY: Final[int] = 2
SUN_LOCATION: Final[Tuple[int, int, int]] = (0, 0, 1000)
SUN_ORIENTATION: Final[Tuple[float, float, float]] = (0.9, 0.9, 0.9)
SUN_SHADOW: Final[int] = 1000

# Tree Parameters
MIN_TREE_SCALE: Final[float] = 0.95  # Relative scale variation
MAX_TREE_SCALE: Final[float] = 1.05  # Relative scale variation
TREE_COLLECTION_NAME: Final[str] = "tree_collection"

# Point of interest parameters
POI_OBJECT_COLLECTION_NAME: Final[str] = "poi_object_collection"  # Collection for the POI models to be instanced
POI_INSTANCE_COLLECTION_NAME: Final[str] = "poi_instance_collection"  # Collection for the POI meshes to instance on

class Prefs:
    """
    Initializes preferences for the tangible landscape plugin
    """
    def __init__(self):
        # Getting settings from JSON
        tlSettings = getSettings()

        # Setting final paths for incoming files
        tlCoupling = tlSettings["folder"]
        self.watchFolder = os.path.join(tlCoupling, WATCH_NAME)
        self.terrainPath = os.path.join(self.watchFolder, TERRAIN_FILE)
        self.waterPath = os.path.join(self.watchFolder, WATER_FILE)
        self.terrainTexturePath = os.path.join(
            tlCoupling, tlSettings["terrain"]["grass_texture_file"]
        )
        self.terrainSidesPath = os.path.join(
            tlCoupling, tlSettings["terrain"]["sides_texture_file"]
        )
        self.waterTexturePath = os.path.join(
            tlCoupling, tlSettings["water"]["texture_file"]
        )
        self.worldTexturePath = os.path.join(
            tlCoupling, tlSettings["world"]["texture_file"]
        )

        # Coordinate Reference System and other configs
        self.CRS = "EPSG:" + tlSettings["CRS"]
        self.timer = tlSettings["timer"]
        self.scale = tlSettings["treeScale"]
        self.treeDensity = tlSettings["treeDensity"]

        # Setting up tree models and textures
        self.trees = []
        for tree in tlSettings["trees"]:
            tree["model"] = os.path.join(tlCoupling, tree["model"])
            tree["input"] = os.path.join(tlCoupling, tree["input"])
            self.trees.append(tree)
        
        # Setting up points of interest and models
        self.pois = []
        for poi in tlSettings["pois"]:
            poi["model"] = os.path.join(tlCoupling, poi["model"])
            poi["input"] = os.path.join(tlCoupling, poi["input"])
            self.pois.append(poi)


class Adapt:
    """
    Contains methods for updating the Blender environment
    based on incoming geospatial data from GRASS
    """
    def __init__(self):
        self.plane = TERRAIN_OBJECT
        self.depressions = WATER_OBJECT
        self.texture = TEXTURE_PATH
        self.dimensions = None
        self.prefs = Prefs()
    
    def terrainChange(self, path: str, CRS: int) -> None:
        """Called to update the blender terrain"""

        # If we need to adjust the view for the first import
        adjustView = bpy.data.objects.get(self.plane) is None
        remove_object(self.plane)  # Removing previous import

        # Bringing in the new terrain data
        print(f'Importing with CRS: {CRS}')
        bpy.ops.importgis.georaster(
            filepath=path,
            importMode="DEM",
            subdivision="mesh",
            step=2,
            rastCRS=CRS,
        )

        # Convert the terrain to a Blender mesh for manipulation
        select_only(self.plane)
        bpy.ops.object.convert(target="MESH")

        # Add sides and materials to the terrain
        self.dimensions = bpy.data.objects[self.plane].dimensions
        add_side(self.plane, "terrain_sides_material")
        # Removing the terrain file
        os.remove(path)

        # Adjusting view if necessary
        if adjustView:
            terrain = bpy.data.objects.get(self.plane)
            adjust_3d_view(terrain)
            adjust_sun(terrain)
    

    def treeChange(self, patchFiles: List[str], watchFolder: str) -> None:
        # Grabbing the geometry node modifier
        terrain = bpy.data.objects.get(self.plane)

        # If the terrain has changed between tree updates
        geoMod = terrain.modifiers.get("tree_mod")
        if not geoMod:
            geoMod = create_tree_geo_nodes(terrain, self.prefs.treeDensity)
    
        for patchFile in patchFiles:
            path = os.path.join(watchFolder, patchFile)

            for i, tree in enumerate(self.prefs.trees):
                if tree["input"].endswith(patchFile):
                    if bpy.data.images.get(patchFile):
                        bpy.data.images.remove(bpy.data.images[patchFile])
                    image = bpy.data.images.load(path)
                    image.pack()

                    # Offset by 1 because the terrain is Socket_0
                    geoMod[f"Socket_{i + 2}"] = image
                    os.remove(path)
                    break
        terrain.update_tag()  # Recalculating the geoNode modifier


    def waterChange(self, path: str, CRS: str) -> None:
        # Removing the old water object and importing a new one
        remove_object(self.depressions)

        try:
            bpy.ops.importgis.georaster(
                filepath=path,
                importMode="DEM",
                subdivision="mesh",
                step=2,
                rastCRS=CRS,
            )
        except Exception:
            pass

        # Converting to a real mesh
        select_only(self.depressions)
        bpy.ops.object.convert(target="MESH")

        # Updating water texture
        water = bpy.data.objects.get(self.depressions)
        waterMaterial = bpy.data.materials.get("water_material")
        water.data.materials.append(waterMaterial)

        # Removing the water file
        os.remove(path)
    

    def pointOfInterestChange(self, poiFiles: List[str], watchFolder: str):
        terrain = bpy.data.objects.get(self.plane)

        # If the terrain has changed between POI updates
        geoMod = terrain.modifiers.get("tree_mod")
        if not geoMod:
            geoMod = create_tree_geo_nodes(terrain, self.prefs.treeDensity)
        
        # Possible creating and then grabbing the instance collection
        if POI_INSTANCE_COLLECTION_NAME not in bpy.data.collections:
            treeCollection = bpy.data.collections.new(TREE_COLLECTION_NAME)
            bpy.context.scene.collection.children.link(treeCollection)
        poiCollection = bpy.data.collections[POI_INSTANCE_COLLECTION_NAME]

        for poiFile in poiFiles:
            path = os.path.join(watchFolder, poiFile)

            for poi in self.prefs.pois:
                if poi["input"].endswith(poiFile):
                    bpy.ops.importgis.shapefile(
                        "EXEC_DEFAULT",                
                        filepath=path,
                        shpCRS=self.prefs.CRS,
                        elevSource="GEOM",  # Change this if our shapefiles have no height
                        separateObjects=False,
                    )

                    select_only(poi["name"])
                    bpy.ops.object.convert(target="MESH")
                    poiObj = bpy.data.objects.get(poi["name"])

                    if poi["name"] in poiCollection.objects:
                        poiCollection.objects.unlink(poiObj)
                        remove_object(poi["name"])  # Removing the old object
                    poiCollection.objects.link(poiObj)

        terrain.update_tag()  # Recalculating the geoNode modifier


class ModalTimerOperator(bpy.types.Operator):
    """Extends Blender Operator which runs interactively from a timer"""

    # Blender Superclass variables
    bl_idname = "wm.modal_timer_operator"
    bl_label = "Modal Timer Operator"
    _timer = 0
    _timer_count = 0

    def modal(self, context: bpy.types.Context, event: bpy.types.Event) -> Dict:
        if event.type == "ESC":
            print("Shutting down operator")
            self.cancel(context=context)
        elif event.type == "TIMER":
            if self._timer_count != self._timer.time_duration:
                self._timer_count = self._timer.time_duration
                fileList = os.listdir(self.prefs.watchFolder)

                # Updating the environment
                try:
                    # Terrain update
                    if TERRAIN_FILE in fileList:
                        self.adapt.terrainChange(self.prefs.terrainPath, self.prefs.CRS)
                    
                    # Water Update
                    if WATER_FILE in fileList:
                        self.adapt.waterChange(self.prefs.waterPath, self.prefs.CRS)
                    
                    # Trees update
                    patchFiles = []
                    for f in fileList:
                        if f in [tree["input"].split("/")[-1] for tree in self.prefs.trees]:
                            patchFiles.append(f)
                    if patchFiles:
                        self.adapt.treeChange(patchFiles, self.prefs.watchFolder)
                    
                    # POI update
                    poiFiles = []
                    for f in fileList:
                        if f in [poi["input"].split("/")[-1] for poi in self.prefs.pois]:
                            poiFiles.append(f)
                    if poiFiles:
                        self.adapt.pointOfInterestChange(poiFiles, self.prefs.watchFolder)
                except RuntimeError as e:
                    print(f"Update failed: {str(e)}")
        
        return {"PASS_THROUGH"}


    def execute(self, context: bpy.types.Context) -> Dict:
        wm = context.window_manager
        wm.modal_handler_add(self)

        # Initializing singleton classes
        self.adaptMode = None
        self.prefs = Prefs()
        self.adapt = Adapt()
        
        self.adapt.realism = "High"

        # Removing all files from the watch directory
        for file in os.listdir(self.prefs.watchFolder):
            try:
                os.remove(os.path.join(self.prefs.watchFolder, file))
            except Exception as e:
                print(f"Could not remove file: {str(e)}")
            
        # Registering and starting the timer
        self._timer = wm.event_timer_add(self.prefs.timer, window=context.window)
        return {"RUNNING_MODAL"}


    def cancel(self, context: bpy.types.Context) -> None:
        # Unregisters and stops the timer
        wm = context.window_manager
        wm.event_timer_remove(self._timer)


class TL_PT_GUI(bpy.types.Panel):
    """Extends Blender Panel to create a custom TL toolbar panel"""

    # Blender superclass variables
    bl_category = "Tangible Landscape"
    bl_label = "Tangible Landscape"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    # Drawing the panel
    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        box = layout.box()
        box.label(text="System Options")
        row = box.row(align=True)
        row.operator("tl.assets", text="Initialize Assets", icon="MESH_CYLINDER")
        row = box.row(align=True)
        row.operator(
            "wm.modal_timer_operator", text="Turn on Watch Mode", icon="GHOST_ENABLED"
        )
        row = box.row(align=True)
        row.operator("tl.clear_trees", text="Clear Trees", icon="REMOVE")


class TL_OT_ClearTrees(bpy.types.Operator):
    """Clear the patch files from the geometry nodes and clear the trees"""

    # Blender superclass variables
    bl_idname = "tl.clear_trees"
    bl_label = "Clear Trees"

    def execute(self, context: bpy.types.Context) -> Dict:
        trees = Prefs().trees
        terrain = bpy.data.objects.get(TERRAIN_OBJECT)

        if terrain:
            geoMod = terrain.modifiers.get("tree_mod")
            if geoMod:
                for i in range(len(trees)):
                    geoMod[f"Socket_{i + 2}"] = None
                terrain.update_tag()  # Refreshing the modifier
                return {"FINISHED"}
        
        print("No trees to clear")
        return {"CANCELLED"}


class TL_OT_Assets(bpy.types.Operator):
    # Blender superclass variables
    bl_idname = "tl.assets"
    bl_label = "Asset Initialization"

    def execute(self, context: bpy.types.Context) -> Dict:
        prefs = Prefs()
        add_sun()
        
        # Creating ground
        create_terrain_material(
            name="terrain_material",
            texturePath=prefs.terrainTexturePath,
            sides=False,
        )

        # Creating sides
        create_terrain_material(
            name="terrain_sides_material",
            texturePath=prefs.terrainSidesPath,
            sides=True,
        )

        # Creating water
        create_terrain_material(
            name="water_material",
            texturePath=prefs.waterTexturePath,
            sides=True,
        )

        create_world(name="TL_world", texturePath=prefs.worldTexturePath)
        bpy.context.scene.world = bpy.data.worlds.get("TL_world")
        bpy.context.space_data.shading.type = "RENDERED"
        bpy.context.space_data.overlay.show_floor = False
        bpy.context.space_data.overlay.show_axis_x = False
        bpy.context.space_data.overlay.show_axis_y = False
        bpy.context.space_data.overlay.show_axis_z = False
        bpy.context.space_data.overlay.show_cursor = False
        bpy.context.space_data.overlay.show_text = False
        bpy.context.space_data.show_gizmo_navigate = False
        bpy.context.space_data.overlay.show_outline_selected = False
        bpy.context.space_data.overlay.show_extras = False
        bpy.context.space_data.overlay.show_object_origins = False

        # Removing default objects in a new Blender scene
        remove_object("Cube")
        remove_object("Camera")
        remove_object("Light")

        # Creating a collection for the trees
        if TREE_COLLECTION_NAME not in bpy.data.collections:
            treeCollection = bpy.data.collections.new(TREE_COLLECTION_NAME)
            bpy.context.scene.collection.children.link(treeCollection)

            # Creating tree objects and linking them to the collection
            for tree in prefs.trees:
                load_tree_from_file(tree["model"], tree["name"], treeCollection, baseSize=prefs.scale)
        
        # Creating a collection for the points of interest
        if POI_OBJECT_COLLECTION_NAME not in bpy.data.collections:
            poiCollection = bpy.data.collections.new(POI_OBJECT_COLLECTION_NAME)
            bpy.context.scene.collection.children.link(poiCollection)
        
        # Instantiate the models alphabetically so they remain in sorted order
        for i, poi in enumerate(prefs.pois):
            load_tree_from_file(poi["model"], f"POI{i} - {poi["name"]}", poiCollection, baseSize=prefs.scale)
        
        # Creating the geometry node system for the trees and pois, if we can
        if TERRAIN_OBJECT in [obj.name for obj in bpy.data.objects]:
            create_tree_geo_nodes(bpy.data.objects.get(TERRAIN_OBJECT), prefs.treeDensity)
        else:
            # Delay creation of geo node modifier
            print("Warning: No Terrain")
            print("Geometry nodes will be initialized later")

        return {"FINISHED"}


class MessageOperator(bpy.types.Operator):
    """Class for raising error messages to the UI"""
    bl_idname = "error.message"
    bl_label = "Message"
    type = StringProperty()
    message = StringProperty()

    def execute(self, context: bpy.types.Context) -> Dict:
        self.report({"INFO"}, self.message)
        print(self.message)
        return {"FINISHED"}
    

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) -> Dict:
        wm = context.window_manager
        # Invoke the popup window
        return wm.invoke_popup(self, width=400, height=1000)


    def draw(self, context: bpy.types.Context) -> None:
        self.layout(self.message)  # Basic popup with message


def remove_object(objectName: str) -> bpy.types.Object:
    obj = bpy.data.objects.get(objectName)
    if obj:
        mesh = obj.data
        bpy.data.objects.remove(obj)  # Removing object
        if obj and type(mesh) == bpy.types.Mesh and mesh.users == 0:
            bpy.data.meshes.remove(mesh)  # Removing mesh if orphaned
        return obj
    return None
    

def select_only(objectName: str) -> bpy.types.Object:
    obj = bpy.data.objects.get(objectName)
    if obj:
        if obj.hide_get():
            obj.hide_set(False)
        
        # Deselecting all objects
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        return obj
    return None


def add_side(objectName: str, materialName: str) -> None:
    terrain = bpy.data.objects.get(objectName)
    fringe = terrain.dimensions.x / 20
    mesh = terrain.data

    # Creating and assigning materials if necessary
    if len(terrain.data.materials) != 2:
        # Should just be able to leave this state like this for the duration of the run.
        terrain_mat = bpy.data.materials.get("terrain_material")
        terrain_sides_mat = bpy.data.materials.get("terrain_sides_material")
        terrain.data.materials.clear()
        terrain.data.materials.append(terrain_mat)  # index 0
        terrain.data.materials.append(terrain_sides_mat)  # Index 1

    # Creating a bmesh copy of the terrain for updates
    bm = bmesh.new()
    bm.from_mesh(mesh)

    # Calculating bounds for the fringe
    x = [v.co.x for v in bm.verts]
    y = [v.co.y for v in bm.verts]
    z = [v.co.z for v in bm.verts]

    xmin, xmax = min(x), max(x)
    ymin, ymax = min(y), max(y)
    zmin = min(z)

    # Setting the fringe
    thresh = 0.1
    for vert in bm.verts:
        if (abs(vert.co.x - xmin) < thresh or
            abs(vert.co.y - ymin) < thresh or
            abs(vert.co.x - xmax) < thresh or
            abs(vert.co.y - ymax) < thresh):
            vert.co.z = zmin - fringe
    
    def faces_side(normal: Vector) -> bool:
        """Determines if the face with the given normal is facing the side"""
        up_dot = normal.dot(Vector((0, 0, 1)))
        down_dot = normal.dot(Vector((0, 0, -1)))
        return (up_dot <= SLOPE_LIMIT and down_dot <= SLOPE_LIMIT)

    # Recompile mesh after modifying fringe
    bm.calc_loop_triangles()

    # Identifying and selecting side faces
    for face in bm.faces:
        for loop in face.loops:
            # Just checking the first loop for speed
            if faces_side(loop.calc_normal()):
                face.material_index = 1
            else:
                face.material_index = 0
            break

    # Reinstantiating mesh and freeing local copy
    bm.to_mesh(mesh)
    bm.free()

    
def adjust_3d_view(object: bpy.types.Object) -> None:
    dst = round(max(object.dimensions)) * VIEW_INCREASE_FACTOR
    
    areas = bpy.context.screen.areas
    for area in areas:
        if area.type == "VIEW_3D":
            space = area.spaces.active
            if dst < 10:
                space.clip_start = 0.1
            if dst < 100:
                space.clip_start = 1
            elif dst < 1000:
                space.clip_start = 10
            else:
                space.clip_start = 100
            
            # Clipping the clip distance to 1e7
            space.clip_end = max(space.clip_end, min(1e7, dst))
            
            bpy.ops.view3d.view_selected()


def adjust_sun(object: bpy.types.Object) -> None:
    """Adjusts the sun based on the new terrain object"""
    dst = round(max(object.dimensions)) * SUN_INCREASE_FACTOR
    bpy.data.objects["Sun"].data.shadow_cascade_max_distance = dst
    bpy.data.objects["Sun"].location.z = dst


def add_sun() -> None:
    sun = bpy.data.lights.new(name="Sun", type="SUN")
    lightObject = bpy.data.objects.new(name="Sun", object_data=sun)
    sun.energy = SUN_ENERGY
    lightObject.location = SUN_LOCATION
    lightObject.rotation_euler = SUN_ORIENTATION
    sun.shadow_cascade_max_distance = SUN_SHADOW
    bpy.context.collection.objects.link(lightObject)


def create_terrain_material(name: str, texturePath: str, sides: bool) -> None:
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes

    # Creating textures
    bsdf = nodes["Principled BSDF"]
    output = nodes["Material Output"]
    texImage = nodes.new("ShaderNodeTexImage")
    texImage.image = bpy.data.images.load(texturePath)

    if not sides:
        texImage.texture_mapping.scale.xyz = TEXTURE_MAPPING_SCALE
    coord = nodes.new("ShaderNodeTexCoord")

    mat.node_tree.links.new(
        coord.outputs["Object" if sides else "UV"], texImage.inputs["Vector"]
    )

    # Link image to shading node color
    mat.node_tree.links.new(bsdf.inputs["Base Color"], texImage.outputs["Color"])
    # Link shading node to surface of output material
    mat.node_tree.links.new(output.inputs["Surface"], bsdf.outputs["BSDF"])
    bsdf.inputs["Roughness"].default_value = TERRAIN_ROUGHNESS


def create_world(name: str, texturePath: str) -> bpy.types.Object:
    world = bpy.data.worlds.new(name=name)
    world.use_nodes = True
    nodes = world.node_tree.nodes

    coord = nodes.new("ShaderNodeTexCoord")
    texImage = nodes.new("ShaderNodeTexImage")
    texImage.image = bpy.data.images.load(texturePath)
    bg = world.node_tree.nodes["Background"]
    output = world.node_tree.nodes["World Output"]

    # Link world node to shader
    world.node_tree.links.new(coord.outputs["Window"], texImage.inputs["Vector"])
    # Link shader color to background color
    world.node_tree.links.new(texImage.outputs["Color"], bg.inputs["Color"])
    # Link background to output surface material
    world.node_tree.links.new(bg.outputs["Background"], output.inputs["Surface"])
    return world


def load_tree_from_file(filepath: str, treeName: str, treeCollection: bpy.types.Collection, baseSize: float = 1.0) -> str:
    bpy.ops.import_scene.gltf(filepath=filepath)
    
    treeObject = bpy.context.active_object
    treeObject.name = treeName
    treeCollection.objects.link(treeObject)

    bpy.data.collections["Collection"].objects.unlink(treeObject)  # Unlinking from main collection

    height = treeObject.dimensions.z
    if height > 0:
        treeObject.scale = tuple([baseSize / height] * 3)
        print(f"Object scale set to {treeObject.scale}")
    treeObject.rotation_euler = (0, 0, 0)
    treeObject.hide_set(True)

    return treeObject.name


def load_poi_from_file(filepath: str, poiName: str, poiCollection: bpy.types.Collection, baseSize: float = 1.0) -> str:
    bpy.ops.import_scene.gltf(filepath=filepath)  # Assuming the POI model is a .glb

    poiObject = bpy.context.active_object
    poiObject.name = poiName
    poiCollection.objects.link(poiObject)



