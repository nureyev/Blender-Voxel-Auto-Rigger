import bpy
import bmesh
import mathutils
from mathutils.bvhtree import BVHTree


ARMATURE_NAME = "Armature"
CAST_LENGTH = .01


def local_to_world_vertex_vector(obj, vertex_vector):
    return obj.matrix_world * vertex_vector


def center_of_polygon(obj, poly):
    vertex_sum = mathutils.Vector((0, 0, 0))

    for vertex_index in poly.vertices:
        vertex_sum += local_to_world_vertex_vector(obj, obj.data.vertices[vertex_index].co)

    center = vertex_sum / len(poly.vertices)

    return center


def center_of_polygons(obj, polygons):
    vertex_sum = mathutils.Vector((0, 0, 0))

    for polygon in polygons:
        vertex_sum += center_of_polygon(obj, polygon)

    center = vertex_sum / len(polygons)

    return center


def center_of_mesh(obj):
    return center_of_polygons(obj,obj.data.polygons)


# factored this out instead of BVHTree.FromObject(...) because I was getting some weird issues with raycasting
def object_to_tree(obj):
    mesh = bmesh.new()
    mesh.from_mesh(obj.data, .5)
    mesh.transform(obj.matrix_world)

    return BVHTree.FromBMesh(mesh)


# returns list of tuples containing the objects and their polygons that touch parameter obj
# TODO : Make this method's return value a little more intuitive
def get_touching_objects(obj):
    touching_objects = []
    tree = object_to_tree(obj)

    for potential_adjacent_obj in bpy.data.objects:
        touching_polygons = []
        if potential_adjacent_obj != obj and potential_adjacent_obj.name != ARMATURE_NAME:
            for polygon in potential_adjacent_obj.data.polygons:
                result = tree.ray_cast(center_of_polygon(potential_adjacent_obj, polygon), polygon.normal, CAST_LENGTH)
                if not all(x is None for x in result):
                    touching_polygons.append(polygon)

            if len(touching_polygons) is not 0:
                touching_objects.append([potential_adjacent_obj, touching_polygons])

    return touching_objects


def weight_object(target_object, armature):
    group = target_object.vertex_groups.new(target_object.name)
    for vertex in range(0, len(target_object.data.vertices)):
        group.add([vertex], 1, 'REPLACE')

    rig_modifier = target_object.modifiers.new('rig_modifier', 'ARMATURE')
    rig_modifier.object = armature


def create_new_standard_bone(target_object, armature, last_bone):

    bpy.ops.object.mode_set(mode='EDIT')
    bone = armature.data.edit_bones.new(target_object.name)
    bone.parent = last_bone

    return bone


def place_standard_bone(target_object, entry_polygons, armature, last_bone):

    bone = create_new_standard_bone(target_object, armature, last_bone)

    bone.head = center_of_polygons(target_object, entry_polygons)
    bone.tail = center_of_mesh(target_object)

    return bone


def rig(armature, last_bone, entry_polygons, last_object, target_object):

    bone = place_standard_bone(target_object, entry_polygons, armature, last_bone)
    target_object.parent = armature

    touching = get_touching_objects(target_object)
    for pair in touching:
        if pair[0].name != last_object.name:
            rig(armature, bone, pair[1], target_object, pair[0])

    weight_object(target_object, armature)


def start_rig_at(target_object):
    bpy.ops.object.add(type='ARMATURE', enter_editmode=True, location=target_object.location)
    armature = bpy.context.object
    armature.show_x_ray = True
    armature.name = ARMATURE_NAME

    bpy.ops.object.mode_set(mode='EDIT')

    bone = armature.data.edit_bones.new(target_object.name)
    bone.tail = center_of_mesh(target_object)
    touching = get_touching_objects(target_object)

    target_object.parent = armature

    vertex_sum = mathutils.Vector((0, 0, 0))
    total_polygons_touching = 0

    # TODO : Refactor this little monstrosity ...
    for pair in touching:
        if pair[0] != target_object:
            rig(armature, bone, pair[1], target_object, pair[0])

            vertex = center_of_polygons(pair[0], pair[1])
            vertex_sum += vertex
            total_polygons_touching += len(pair[1])
    center = vertex_sum / total_polygons_touching

    bone.head = center

    weight_object(target_object, armature)

