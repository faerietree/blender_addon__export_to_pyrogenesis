#-------------------------------------------------------------------------------
#!/usr/bin/env python
# ========= BLENDER ADD-ON =====================================================

bl_info = {
    "name":         "Selection 2 0AD Actors",
    "author":       "faerietree (Jan R.I.Balzer-Wein)",
    "version":      (0, 1),
    "blender":      (2, 7, 1),
    "location":     "View3D > Tool Shelf > Selection 2 0AD Actors",
    "description":  "Either creates a set of 0AD actor files of the selected objects"
            " (including group instances which are resolved to their source objects)."
            "Or selects all objects of the current"
            " scene that are not hidden automatically while sorting out rendering-"
            " or animation-related objects like lighting, cameras and armatures."
            " \r\n\nIf no 'subfolder:<Material>' is given in the object- or groupname"
            " then the xml file will be created in the highest level actor/ folder.",
    "wiki_url":     "http://wiki.blender.org/index.php/Extensions:,"
                    "2.7/Py/Scripts/Import-Export/Selection20ADActor",
    "tracker_url":  "https://projects.blender.org/tracker/index.php?"
                    "func=detail&aid=",
    "category": "Import-Export"
    #,"warning":      ""
}


# ------- INFORMATION ----------------------------------------------------------
# First created for Blender Version: 2.71
#
# Addon-Version: v.1 - 2014-07-19
# Author: Ian R.I.B.-Wein, known as Radagast of Arda, FairieTale Productions
#

# ------- DESCRIPTION ----------------------------------------------------------
#
# """PURPOSE"""
# GENERATING 0AD VISUAL ACTOR XML FILES + EXPORTING CORRESPONDING MESHES AS .DAE.
#
#
# """WHAT IT DOES"""
# Depending on settings: (default setting is to not include all parent objects)
#
# - either iterate selected objects and its children recursively, creating
#   a 0ad_actor xml file in path/to/0ad/mods/<new mod per export>/actors/ .
#   where the actors' props are derived from the actor object's children.
#
# - or the above and additionally first climb up the tree to all the parent objects.
#

# ------- LICENSING ------------------------------------------------------------
# (c) Copyright FarieTree Productions J. R.I.B.-Wein    jan@ardaron.de
# It's free, as is, open source and property to Earth. But without warranty.
# Thus use it, improve it, recreate it and please at least keep the
# origin as in usual citation, i.e. inclucde this Copyright note.
# LICENSE: CC-BY-SA
#
# ------------------------------------------------------------------------------



#------- IMPORTS --------------------------------------------------------------#
import bpy
import re
import os

from bpy.props import IntProperty, StringProperty, BoolProperty, EnumProperty




#------- GLOBALS --------------------------------------------------------------#
#show debug messages in blender console (that is the not python console!)
debug = True

#both independant, for the input-globals see register()!
case_sensitive = True
#write_to_file = True

#difficult to guess unless animation or rendering-related
skip_non_mechanical_objects = True

#whether to resolve groups and create BoM entries for contained objects
#set in context view 3d panel
after_how_many_create_actor_recursions_to_abort = 100#kind a century :)


filelink = None

header = '<?xml version="1.0" encoding="utf-8"?>'
header = header + "\n" + '<actor version="1">'

header_ = '</actor>'



#------- FUNCTIONS ------------------------------------------------------------#
#COMMAND BASE FUNCTION
def main(context):
    
    #processInput(context)
    act(context)
    return {'FINISHED'}





#ACT
#@param string:unix_pattern is optional
#@return always returns True or False#selection_result
object_reference_count = {}
def act(context):

    if debug:
        print('engine started ... (acting according to setting)')
    ############
    #preparation - selection
    ############
    
    #----------#
    # At this point a selection must have been made either using
    # 'select by pattern' add-on or by manually selecting the objects/items.
    #----------#
    # Otherwise an effort is undertaken to automatically select mechanical parts.(visible only):
    if (context.selected_objects is None or len(context.selected_objects) == 0):
        #if debug:
        print('No selection! Automatically guessing what to select. (hidden objects are not selected)')
        #ensure nothing is selected
        bpy.ops.object.select_all(action="DESELECT")
        if debug:
            print('deselecting all.')
        #select depending on if it is a mechanical object (TODO)
        for o in context.scene.objects:
            if debug: 
                print('Scene object: ', o)
            if (o.hide):#here we skip hidden objects no matter settings as this way
                # one has the choice to either include object via selecting or
                # or exlude objects by hiding those.
                if debug:
                    print('Auto-selection: Hidden scene object ', o, '.')
                continue
            if (o.type != None):
                if debug:
                    print('Type of scene object: ', o, ' = ', o.type)
                #dupligroup/groupinstance can theoretically be attached to any object, but we only consider those:
                if (not is_object_type_considered(o.type)):
                    continue
                is_longest_object_label_then_store_len(o)  #keep track of longest label length
                is_longest_material_then_store_len(material=o.active_material)
                o.select = True #select object
                context.scene.objects.active = o    #make active
                if debug:
                    print('Selected object: ', o, ' \tactive object: ', context.scene.objects.active)
                    
        #select object instances depending on if it is a mechanical object (TODO)
        for ob in context.scene.object_bases:
            if debug: 
                print('Scene object base: ', ob)
            o = ob.object
            if (o.hide):#here we skip hidden objects no matter settings as this way
                # one has the choice to either include object via selecting or
                # or exlude objects by hiding those.
                if debug:
                    print('Auto-selection: Hidden underlaying object ', o, ' of object base ', ob, '.')
                continue
            if (o.type != None):
                if debug:
                    print('Type of scene object: ', o, ' = ', o.type)
                if (not is_object_type_considered(o.type)):
                    continue
                #increase the counter for this object as another reference was found?
                if (not (o in object_reference_count)):# || object_reference_count[o] is None):
                    object_reference_count[o] = 0
                object_reference_count[o] = object_reference_count[o] + 1
                #keep track of the longest label's length
                is_longest_object_label_then_store_len(o)
                is_longest_material_then_store_len(material=o.active_material)
                #select the object reference TODO object or the reference which one to select?
                ob.select = True  #select object
                context.scene.objects.active = o    #make active
                if debug:
                    print('Selected object: ', ob, ' \tactive object: ', context.scene.objects.active)



    ############
    # Now there must be a selection or we abort the mission.
    ############
    #Now at last we have a selection? Either set up manually or selected automatically.
    if (len(context.selected_objects) == 0):
        if debug:
            print('Selection is still empty! Mission aborted.')
        return {'CANCELLED'}
        

    

            
    
    # Find all highest level parents if setting isn't otherwise. Else that each selected object is the highest :
    distinct_parents_of_selected_objects = []
    for obj in context.selected_objects:
        # Optionally travel up the hierarchy automatically. Else each selected object is assumed to be the highest to be exported.
        if (not context.scene.export_to_0ad__auto_resolve_parent):
            distinct_parents_of_selected_objects = context.selected_objects.copy()
        else:
            childOrHighest = obj
            while (childOrHighest.parent):
                childOrHighest = childOrHighest.parent
            # We have reached the highest level parent once the childOrHighest hasn't any parent.
            if (not distinct_parents_of_selected_objects.contains(childOrHighest)):
                distinct_parents_of_selected_objects.append(childOrHighest)
    
    # If only one main actor is exported at once, then there will only be one distinct parent:
    for distinct_parent in distinct_parents_of_selected_objects:
        # Start with the determined highest level parent: 
        last_created_actor = export_actor_related_files_recursively(obj)
        #if (file_exists(last_created_actor.filelink)):
        print('Created actor: ' + last_created_actor)
        
    return True
        

    ##########
    # GROUPS (not group instances, those are attached to objects and therefore already handled above when iterating the scene objects!)
    ##########
    #Groups are not represented by any data in a scene. As such it's no problem if the objects in a scene are wildly grouped.
    #Those groups will have no influence on the generated Bill of Materials (BoM). Only instances have an effect.
    #The effect of group instances is twofold:
    #1) Instances are high level parts, containing objects, i.e. other parts.
    #2) Instances are self-contained standalone parts.
    
    #(And should not be resolved. => Here the material has to be specified explicitely or will be stated as mixed.)
    
    #global bom_entry_count_map
    #bom_entry_count_map = {}    #clear the map/dictionary --> now appending to the already created BoM for objects/group instances.
    append_to_file(context, "\r\n\n\nGROUPS OF SCENE\r\n")
    #TODO Create separate bom_entry_count_map for groups, because until now here several lines are added redundantly!
    
    
    for g in bpy.data.groups:#bpy.types.BlendData.groups:

        #examine if all objects are in the current context scene
        are_all_objects_in_context_scene = True
        for o in g.objects:
            if not o.is_visible(context.scene):
                are_all_objects_in_context_scene = False
                break#cancel further examination
        
        #Is this group not completely in the current/context scene?
        if (not are_all_objects_in_context_scene):
            if debug:
                print('Not all objects of this group ', g, ' are (visible) in this scene: ', context.scene)
            continue#next Group within the blend file
            
        #Add this group to the bill of materials as standalone complete part on its own (not resolving to objects)?
        if (not context.scene.selection2actors_in_mode == '0'):#not resolve_groups):
            #group has a partname identifier and this hopefully contains a material:<material>,
            # => try to compile a bom entry out of this, if not possible then lookup the material from the objects,
            # => i.e. either compose a list of materials being used in the group (Aluminium, Stainless Steel, Diamond)
            #         or give a label like 'mixed'.
            # If no material can be resolved then use 'undefined' or rather '-'.
            bom_entry = build_and_store_bom_entry_out_of_group(context, g)
            append_to_file(context, bom_entry)
            #resolve all group instances created out of this group:
            for o_g in g.users_dupli_group:
                #examine group instance
                if o_g.dupli_group is None or len(o_g.dupli_group.objects) == 0:
                    if debug:
                        print('dupli group/group instance was None/null or no objects'
                                'were contained. Object count: ', len(o_g.dupli_group.objects))
                    continue
                
                bom_entry = build_and_store_bom_entry(context, o_g)
                #build_bom_entry() is not enough as we have to keep track of the occurence counts => and store
                append_bom_entry_to_file(context, bom_entry)
        
            
            continue#no further examination of the group's objects
        
        #######
        # RESOLVE GROUP TO OBJECTS
        #######
        #Then in this mode all the objects that make up the group are put into the bill of materials separately.
        for o in g.objects:
            bom_entry = build_and_store_bom_entry(context, o)
            #build_bom_entry() is not enough as we have to keep track of the occurence counts => and store
            append_bom_entry_to_file(context, bom_entry)
            

        

        
    #Everything was fine then!
    return True#selection_result
    
    ############
    #act-furthermore
    ############
    #nothing so far ..
    #but a smiley :) highly underestimated



#
#
#
all_exported_actors = []
create_actor_recursion_depth = 0
def export_actor_related_files_recursively(o):
    global all_exported_actors  # To allow writing access to the global variable.
    global create_actor_recursion_depth
    create_actor_recursion_depth = create_actor_recursion_depth + 1
    
    if (create_actor_recursion_depth > after_how_many_create_actor_recursions_to_abort):
        if debug:
            print('Failed creating all actors and their related files in time. Recursion limit exceeded: '
                    , create_actor_recursion_depth)
        return {'CANCELLED'}

    if debug:
        print('Encountered: ', o, ' type: ', type(o))
   

    #termination condition will be checked here:
    #-------
    # LIST?
    #-------
    if (o is list or type(o) is list):
        for o1 in o:
            create_bom_entry_recursively(context, o1)
        return {'FINISHED'}


    #-------
    # OBJECT?
    #-------
    elif ( (o is object) or (type(o) is object) or (type(o) is bpy.types.Object) ):
        
        is_longest_object_label_then_store_len(o)
        print('Encountered an object: ', o, ' blender-Type: ', o.type)
        
        
        #Is object type considered? (not considered are e.g. armatures.)
        #dupligroup/groupinstance can theoretically be attached to any object, but we only consider those:
        if (is_object_type_considered(o.type)):#(o_bjects has to be an object for type to exist)

            #Is not a group instance?        
            if (o_bjects.dupli_group is None):
                    #or o_bjects.dupli_type is not 'GROUP'<--TODO:superfluous? What effects does changing the duplitype setting have?
                if (not o_bjects.is_visible(context.scene)):
                    if debug:
                        print('Object ', o,' is not visible in the current scene: ', context.scene)
                    return {'CANCELLED'}
                    
                #this object is not functioning as a group instance container!
                if (not build_and_store_bom_entry(context, o)):
                    if debug:
                        print('Failed to write bom entry to file. ', o, create_bom_entry_recursion_depth)
                    return {'CANCELLED'}
                    
                return {'FINISHED'}


            #NOTE: PAY ATTENTION TO BLANK LINES - COMPILER COULD ASSUME THE ELIF STATEMENT IS ALREADY DONE.
            
            #Is a group instance?
            elif (o.dupli_group is not None
                    #and o_bjects.dupli_type is 'GROUP'<--TODO:superfluous? What effects does changing the duplitype setting have?
                    #THE DUPLI_TYPE IS ONLY RELEVANT FOR NEWLY CREATED DUPLICATIONS/REFERENCES FROM THE OBJECT!
                    #THE TYPE OF THE GROUP (o_bjects.dupli_group:bpy.types.Group) IS INTERESTING BUT IS 'GROUP' ANYWAY ELSE IT WERE NO GROUP!
                    #Is a group but has no objects in the group?
                    and (len(o.dupli_group.objects) > 0)): #if no objects are linked here the creation of a BoM entry is pointless
                if debug:
                    print("It's a Group instance! Attached dupli group: ", o.dupli_group)
                    
                #Resolving groups is not desired?
                if (context.scene.selection2actors_in_mode == '0'):
                    if debug:
                        print('Group shall not be resolved. Is considered a standalone complete part on its own.')
                    #This object is functioning as a group instance container and resembles a standalone mechanical part!
                    if (not build_and_store_bom_entry(context, o)):
                        if debug:
                            print('Failed to write bom entry of group instance to file: ', o, '\t dupli group: ', o.dupli_group)
                        return {'CANCELLED'}
                    return {'FINISHED'}
                    
                #make an attempt at resolving the group instance
                #Here only group instances are handled! Groups are handled later in the act function.
                #The objects where this instance is attached to?
                resolve_group_result = o.dupli_group.objects#resolve_group(group)
                
                if (resolve_group_result is None or (len(resolve_group_result) < 1)):
                    #Group was not resolved successfully!
                    if debug:
                        print('Failed to resolve a group or group was empty. ', group)
                    return {'CANCELLED'}
                    
                #Group resolved into objects!
                if debug:
                    print('Resolved a group. Count of objects in group: ', len(resolve_group_result))
                for obj in resolve_group_result:
                    create_bom_entry_recursively(context, obj)
                    
                return {'FINISHED'}
                    
            else:
                #if no objects are linked here the creation of a BoM entry is pointless
                if debug:
                    print('It may be a group instance ', o.dupli_group, ' but has no objects: ', o.dupli_group.objects)
                return {'CANCELLED'}
            
            
            
        #Object type is not considered then:
        else:
            if (debug):
                print('Object type ', o.type, ' is not considered (e.g. armatures are not considered a mechanical part).')
            return {'CANCELLED'}
            
        
    #if we didn't return until now, then this time none of the above conditions was met:
    if debug:
        print('Did not match any branch for creating an actor file:', o, ' type:', type(o))


    ############    
    # Filelink is derived from parent object name in this level depth.
    # Both .xml for the actor and .dae for the mesh are required and 
    # should have a consistent subfolder structure as both are content paths.
    ############
    mesh_filelink = target_mod_path + "art/meshes/" + target_subfolder + "/" + tidyUpName(o.name) + ".dae"
    texture_output_directory = target_mod_path + "art/textures/skins/" + target_subfolder + "/"# + o.data.uv_textures.active.name #+ ".png"
    

    actor = Actor()  # implicitely calling the Actor class' __init__ method. (the constructor)
    
    ##########
    # OBJECTS (including group instances as those are attached to objects, see dupligroup 
    #          http://wiki.blender.org/index.php/Doc:2.6/Manual/Modeling/Objects/Duplication/DupliGroup)
    ##########
   
    #TIDY UP ACTOR VARIANTS XML (Summarize)
    # Figure variants, highly redundant, i.e. each mesh has a variant for each of its UV assigned textures:
    variants = []
    object_prefix = o.name.split("__")[0] #getBaseName() #separated_by_double_underscore to allow for single underscores.
    # If highest automatic highest level parent resolving is deactivated, then this may well be a custom selection we shall operate on:
    if (not context.scene.export_to_0ad__auto_resolve_parent):
        object_references = context.selected_objects.copy()
    # Else we search all equal-prefixed object from within the full set of this scene's objects. (TODO From visible layers only.)
    else:
        object_references = context.scene.objects
    
    # all other variant properties depend on the mesh variants, i.e. variant objects and their textures and props:
    all_objects_with_this_prefix = filterObjectsByRegex(object_references,
            '^' + object_prefix)
    # <-- the mesh variants,i.e. collada filelinks can be derived from the objects directly without export as all existing files will be overridden using the objectname, never changing it!
                                                     # no deepcopy as the objects in the dictionary
                                                     # shall keep their live character, i.e. stay a reference!
                                                     # This was required because we have to create new
                                                     # temporary selections later on while diving
                                                     # deep in the create_bom_entry_recursion adventure!
    all_objects_with_this_prefix_index = -1
    # form it into variants : #TODO Properly group it in the toXml() method.
    
    while ++all_objects_with_this_prefix_index < len(all_objects_with_this_prefix):
        object_with_this_prefix = all_objects_with_this_prefix[all_objects_with_this_prefix_index]
        
        if (object_with_this_prefix.type != 'MESH'):
            continue
        

        # create the variant for this mesh: (each variant will get the uv_map's name to allow for picking the correct variant according to unit state)
        variant = Variant()
        # build output filename:
        mesh_filepath_parts = object_with_this_prefix.split("##")
        # each non-empty part is a part of the filelink:
        mesh_filepath_parts_index = -1
        # no subfolders?
        variant.mesh = OUTPUT_PATH_BASE_ABSOLUTE + "/" + OUTPUT_SUBFOLDER
        mesh_filepath_parts_length = len(mesh_filepath_parts)
        if (mesh_filepath_parts_length < 1):
            print('No subfolders given in object name. Will use highest level output folder + specified global subfolder.')
        else:
            while (++mesh_filepath_parts_index < mesh_filepath_parts_length - 1): # - 1 because the last is no subfolder
                object_specific_subfolder = mesh_filepath_parts[mesh_filepath_parts_index]
                variant.mesh += "/" + object_specific_subfolder
        mesh_filename = mesh_filepath_parts[mesh_filepath_parts_length - 1] + ".dae"
        variant.mesh += mesh_filename
        
        texture_variants = {}
        # one (the 2nd!) UV map for ao and one for diffuse (the 1st): all others are seen as variants but are omitted currently. TODO how to distinguish texture types and variants. TODO Use _norm and _ao to figure it out? !! NO! => Those are generated, thus this indeed are variants and not textures.
        # => Texture variants are assigned to the same UV map.
        uv_textures = []
        uv_textures = object_with_this_prefix.data.uv_textures
        for mesh_texture_polylayer in uv_textures.items: 
            uv_map_name = mesh_texture_polylayer.name
            print('uv_map_name: ' + uv_map_name)
            # iterate each quad or poly (since BMesh is supported by blender, i.e. since 2.61+)
            for mesh_texture_poly in mesh_texture_polylayer.data: # type of mesh_texture_poly is Image
                texture_variant = Variant()
                texture_variant.name = uv_map_name + '' + rand()
                texture_variant.textures.append(mesh_texture_poly.filepath)
                # file_format UPPERCASE
                # TODO if image not exists in textures/skins/... output directory, then create it:
                parts = mesh_texture_poly.filepath.split("\/");
                output_filelink = texure_output_directory + parts[len(parts) - 1];
                print('output_filelink: ' + output_filelink)
                if not file_exists(output_filelink):
                    mesh_texture_poly.data.save_render(output_filelink)
                

        for texture_variant in texture_variants:
            variants.append(texture_variant) 
        #################
        # Build props:
        #props_actors = [] #"<props>"
        children_index = -1
        while ++children_index < len(o.children):
            child_object = o.children[children_index]
            # Note: Curves are converted to mesh.
            if (not is_object_type_considered(child_object.type)):
                print('object type: ' + child_object.type + ' is marked as not to be considered.')
                continue
            if (child_object.type == "EMPTY"):
                # It will be selected in the next while loop, but it may be possible that empties have children, but still empties somehow had to be skipped and their children exported instead and all those child actor filepaths then need to be returned instead of the single empty-filepath (which doesn't exist as empties are prop points and don't exist in their standalone .dae file but only in their parent object's .dae file.).
                additional_props = [] 
                for child_child in child_object.children:
                    print("Exporting children of EMPTY child objects not yet guarantueed to generate valid output.")
                    child_child_prop = Prop()
                    child_child_prop.actor = export_actor_related_files_recursively(child_child)
                    child_child_prop.attachpoint = "prop-" + child_child.name # TODO That this will be the correct attachpoint name can't be guarantueed this way at all!
                continue
            # It's a mesh or curve:
            child_actor = export_actor_related_files_recursively(child_object)
            
        # Now we select all that is required to be exported as COLLADA .dae: 
        # That are the main object/mesh + its child empties, post processed (modifiers applied et alia).
        # If the main object/mesh is a group instance (if a dupligroup is attached), then we resolve it, duplicate all recursively with its children, apply all modifiers and join them into one single mesh.
        children_index = -1
        # deselect all because we need to only have a clean selection of this recursion level depth's object + its empty children.
        bpy.ops.object.select_all(action="DESELECT")
        bpy.ops.object.select(o)
        while ++children_index < len(o.children):
            child_object = o.children[children_index]
            # also select its predefined prop points (child empties): Then duplicate all those. 
            if (child_object.type == 'EMPTY'):
                child_object.select = True
                continue 
            # in blender it is ensured that this name assignment is successful, while other equal named empties might get renamed.
            # Note: It is important that this does not happen in the upper while loop where we recurse on each child as each recursion layer may change the selection or the name as other objects are added with maybe identical names! Otherwise this might be a hard to find bug!
            # it's a mesh child: (add a prop point empty)
            prop = Prop()
            #prop_point_name = add_prop_point_at_child_object_origin(child_object)
            bpy.ops.3dview.cursor_to_selected()
            bpy.ops.object.add('EMPTY')
            prop_point_object = context.active_object
            prop_point_object.parent = child_object_duplicate
            prop_point_object.name = "prop-" + child_object.name
            prop.attachpoint = child_object.name
            
            

            # it's an empty
            child_object.select = True
        
        # Before export:
        #setCursorToCenter()
        object_duplicate.location = (0.0, 0.0, 0.0) # <-- child objects inherit this location. TODO check in the 0AD Atlas if the children's location has to be applied. 
        bpy.ops.object.apply_modifiers()#child_object_duplicate)
            selectedOnly = True
        bpy.ops.object.export_collada(variant.mesh, selectedOnly)#child_object_duplicate is the active object, thus selected and will be exported)
        bpy.ops.object.collada_export(variant.mesh, selectedOnly)
            prop.actor = child_actor.filelink
            # derive attachpoint by exporting this child_object to .dae:
            prop.attachpoint = prop_point_name
            
            variant.props.append(prop)
        variants.append(variant)


    # determine commons of all variants: (If we wanted to simplify, then we could pack it all into one group containing redundant variants. That'd be the easy way. We take the difficult, but less redundant branch. Note: Within one variant, attaching to the same attachpoint adds yet another prop to this point, while the first attachment to a prop-point in a variant will overwrite the other props that may have been attached by other selected variants of other (previous) groups.)
    variant_containing_all_that_is_common = Variant()
    #TODO determine commons: meshes, animations, textures, props (static garrisoning, i.e. non-simulation interactive), ...
    # (remove found commons from their original variant in the process).
    moveVariantCommonsToANewVariant(variants, variant_containing_all_that_is_common) # <-- that's an additional variant!
    # Note: ^ modifies both variants and the new common variant as they are given by reference!

    base_group = Group()
    base_group.variants.append(variant_containing_all_that_is_common)
    
    # usually two:
    # 1x the base group (containing exactly 1 variant that contains all that is common to all variants),
    # 1x the group containing all other variants. (TODO Maybe even logically sub-distinguish this group further by creating more groups?)
    variants_distinct_group = Group()
    variants_distinct_group.variants.append(variants)
    #TODO distinct_variant_groups_settled_upon = furtherSubdivideTheVariantGroup(variant_group)
    

    actor.groups = []
    actor.groups.append(base_group)
    actor.groups.append(variants_distinct_group)
    ## TODO add all logical groups, i.e. the variants logically grouped (e.g. by textures, meshes, animation, props, ... e.g. all textures as a variant but Attention: That only works if EACH mesh is compatible with EACH texture. And so on.)
    #for g in distinct_variant_groups_settled_upon:
    #    actor.groups.append(g)
    


    
    
    actor_filelink = target_mod_path "art/actors/" target_subfolder "/" tidyUpName(o.name) ".xml" #build_filelink(context)
    if (write2file(actor.toXml(), actor_filelink)):
        print('=> Created actor file: ' + actor + ' with content: ' + actor.toXml()) 
        all_exported_actors.append(actor)
        
    return actor #TODO The groups (group instances) still show up redundantly (1x <group1>
                                                                                    # 2x <group1>
                                                                                    # 1x <group2>)





#
#
#
object_longest_label_len = 0
def is_longest_object_label_then_store_len(o):
    global object_longest_label_len
    #keep track of the longest object name to fill up with zeros not to break the bill of materials structure:
    o_label = getBaseName(o.name)
    letter_count = len(o_label)
    if (letter_count > object_longest_label_len):
        object_longest_label_len = letter_count
    if debug:
        print("Keeping track of longest object label's length. Longest length: ", object_longest_label_len)






#
#
#
material_longest_label_len = 0
#def is_longest_material_then_store_len(material):
def is_longest_material_then_store_len(material_label='', material=None):
    global material_longest_label_len
    if (material is None and material_label == ''):
        return False
    #keep track of the longest material name to fill up with zeros not to break the bill of materials structure:
    m_label = '-'
    if (material is None):
        m_label = getBaseName(material_label)
    else :
        m_label = getBaseName(material.name)
        
    letter_count = len(m_label)
    if (letter_count > material_longest_label_len):
        material_longest_label_len = letter_count
    if debug:
        print('Keeping track of longest material label\'s length. Longest length: ', material_longest_label_len)





    
    return {'FINISHED'}



#
# If a object type is considered or rather if an object type is ignored, i.e. filtered out.
# This is useful for skipping animation related objects which shall e.g. not occur in a BOM.
#
def is_object_type_considered(object_type):
    #dupligroup/groupinstance can theoretically be attached to any object, but we only consider those:
    return object_type == 'MESH' or object_type == 'EMPTY' or object_type == 'CURVE'
            #TODO type is not related to being mechanical part or not!
            #or not skip_non_mechanical_objects;#<- overwrites the above and renders all types valid
    #EMPTY for group instances (even though instances can be attached to any other than empty object too!)




#
# Builds a BOM ENTRY from an object.
# If a dupligroup/instance is attached to the object, this group is:
#   1) either resolved to its original group and the objects within this group are put into the BoM,
#   2) or the group instance's name is parsed for a assigned material (as a group does not have a material assigned directly)
#      or the material is resolved from contained objects or a the material 'mixed' or 'undefined' is assigned.
# It is being examined how often objects occur to calculate the part count.
# ATTENTION: better don't use user_count blender python API variable because it's not sure that all those user references
# were within the current scene or file or if it was selected anyways!


#def write_bom_entry_to_file(context, o):
#    bom_entry = build_bom_entry(context, o)
#    return write2file(context, bom_entry)
    #ATTENTION: BETTER FIRST CREATE ALL BOM ENTRIES, STORING THEM IN THE UNIQUE ENTRY LIST,
    #INCREMENTING THE EQUAL BOM ENTRY COUNT AND ONLY THEN WRITE THIS TO FILE!
  
  
  
bom_entry_count_map = {}
#def init_bom_entry_count_map():
#   pass
def build_and_store_bom_entry(context, o):#http://docs.python.org/2/tutorial/datastructures.html#dictionaries =>iteritems()
    bom_entry = build_bom_entry(context, o)#http://docs.python.org/3/tutorial/datastructures.html#dictionaries => items() 
    if debug:
        print('Generated BoM entry: ', bom_entry)
    
    #keep track of how many BoM entries of same type have been found
    if (not (bom_entry in bom_entry_count_map)):
        if debug:
            print('From now on keeping track of bom_entry count of ', bom_entry)
        bom_entry_count_map[bom_entry] = 0
    
    bom_entry_count_map[bom_entry] = bom_entry_count_map[bom_entry] + 1
    if debug:
        print('-> new part count: ', bom_entry_count_map[bom_entry], 'x ', bom_entry)
    return bom_entry
    
    
    
 
#    
#g: bpy.types.Group not a group instance, i.e. no object with dupli group bpy.types.Group attached
def build_and_store_bom_entry_out_of_group(context, g):
    #return build_and_store_bom_entry_out_of_group(context, g)
    return '\r\nBuilding bom entry out of group not supported yet. Possibly solve it analoguously to group instance dimension resolving.'

    

def build_bom_entry(context, o):    
    #build BoM entry: using http://www.blender.org/documentation/blender_python_api_2_69_release/bpy.types.Object.html
    entry = getBaseName(o.name)
    
    index = -1
    material = '-'
    if (o.active_material is None):
        if debug:
            print('Object ', o, ' has no active material.')
        if (not (o.dupli_group is None)):
            print('It\'s a dupli group attached to this object. => This is a group instance. => Resolving material from its objects.')
            found_material_within_group_objects = False
            for group_object in o.dupli_group.objects:
                if (not (group_object.active_material is None)):
                    found_material_within_group_objects = True
                    material = getBaseName(group_object.active_material.name)
                    break#leave the loop as we have achieved our goal
            if (debug and not found_material_within_group_objects):
                print('Found no next best material within the attached group object members: ', o.dupli_group.objects)
    else:
        material = getBaseName(o.active_material.name)    #default value
        
    #look for a material explicitely specified:
    index = o.name.find('material:')
    if (index != -1):
        parts = o.name.split('material:')
        if (len(parts) > 1):
            material = parts[1]     #material given explicitely, e.g. Aluminium (Isotope XY)
        entry = parts[0]            
    else:
        index = o.name.find('Material:')
        if (index != -1):
            parts = o.name.split('Material:')
            if (len(parts) > 1):
                material = parts[1]
            entry = parts[0]
        else:
            index = o.name.find('mat:')
            if (index != -1):
                parts = o.name.split('mat:')
                if (len(parts) > 1):
                    material = parts[1]
                entry = parts[0]
            else:
                index = o.name.find('Mat:')
                if (index != -1):
                    parts = o.name.split('Mat:')
                    if (len(parts) > 1):
                        material = parts[1]
                    entry = parts[0]
                else:
                    index = o.name.find('M:')
                    if (o.name.find('M:') != -1):
                        parts = o.name.split('M:')
                        if (len(parts) > 1):
                            material = parts[1]
                        entry = parts[0]
                    else:
                        index = o.name.find('m:')
                        if (index != -1):
                            parts = o.name.split('m:')
                            if (len(parts) > 1):
                                material = parts[1]
                            entry = parts[0]
                
    #keep track of the longest material label
    is_longest_material_then_store_len(material_label=material)
    
    #dimensions
    context.scene.objects.active = o
    result = {'CANCELLED'}
    operations_to_undo_count = 0
    #if (not (context.active_object is None)):
    #    #because multi-user mesh does not allow applying modifiers
    #    if (bpy.ops.object.make_single_user(object=True, obdata=True)):#, material=True, texture=True, animation=True)):
    #        operations_to_undo_count = operations_to_undo_count + 1
    #        for m in o.modifiers:
    #            result = bpy.ops.object.modifier_apply(modifier=m.name)
    #            #bpy.ops.object.modifier_apply()#'DATA', '')#applies on the active object
    #            if (result):
    #                operations_to_undo_count = operations_to_undo_count + 1
    
    
    #######
    # DIMENSIONS
    #######
    #TODO don't take the absolute bounding_box dimensions -instead calculate form object.bounding_box (list of 24 space coordinates)
    #A group instance? (dupli group empties/objects where a dupli group is attached may have no dimensions or zero).
    #undo_count = 0 #now working with a copy of the initially selected_objects (no longer a live copy/reference)
    x = o.dimensions[0]
    y = o.dimensions[1]
    z = o.dimensions[2]
    if (not (o.dupli_group is None)):
        if debug:
            print('Creating temporary selection.')#To be undone or unexpected results will
            # occur as the loop uses a live copy of selection. <-- No longer valid!
            # Now using a copy of the dict for the recursion create_bom_entry_recursively.
        
        #ensure nothing is selected
        if (not bpy.ops.object.select_all(action="DESELECT")):
            print('There seems to be already no selection - that may be interesting, but as we work with a copy it should not matter. Of importance is that now nothing is selected anymore.')
        #undo_count = undo_count + 1
        o.select = True
        #undo_count = undo_count + 1
        
        #BELOW THIS LINE NOTHING HAS TO BE UNDONE! AS THIS DUPLICATED OBJECT
        #(GROUP INSTANCE) WILL SIMPLY BE DELETED AFTERWARDS.
        if (not bpy.ops.object.duplicate()):#non-linked duplication of selected objects
            print('duplicate failed')
            
        if (len(context.selected_objects) > 1):
           print('Only one object (the group instance) should have been selected.\r\nSelection: ', context.selected_objects, '. Thus dimension will only reflect those of the dupli group objects of the first selected group instance object.')
        context.scene.objects.active = context.selected_objects[0]
        if debug:
            print('active object after duplication of group instance: ', context.active_object, ' or :', context.scene.objects.active)
     
        # That this condition is true is very UNLIKELY!  
        if (context.scene.objects.active.dupli_group is None):
            print('The active object is no group instance after the duplication for determining dimension!? Looking for a group instance in selection now ...')
            is_group_instance_found = False
            #This loop is a not very likely as we have or rather should only one object in the selection!
            for selected_o in context.selected_objects:
                if (not(selected_o.dupli_group is None)):
                   context.scene.objects.active = selected_o
                   is_group_instance_found = True
                   print('found ', selected_o)
                   break
                else:
                   selected_o.select = False#TODO is that a good idea or even required?
            if (not is_group_instance_found):
                print('No group instance found in temporarey selection. Aborting ...')

        
        #the active object (group instance) should be the only selected one:
        bpy.ops.object.duplicates_make_real(use_base_parent=True)#false because we don't set up
                #the empty group instance as parent of the now copied and no longer referenced group objects!
                #The dupli group attached to this object
                #is copied here as real value object copies (not references).
        
        #new group instance hopefully is the active object now:
        group_objects_count = 0
        for group_object in context.scene.objects.active.children:#dupli_group.objects:
            if (group_object.type == 'EMPTY' or group_object.type == 'Armature'):
                #and is_object_type_considered(group_object_type)):
                print ('Warning: Group object\'s type is EMPTY or ARMATURE. Skipping it as these have no dimensions anyway.')
                continue
            if (not group_object.type == 'MESH'):
                group_object.select = False #required because of joining only allows mesh or curve only - no mix!
            group_object.select = True
            ++group_objects_count
        #Note:
        # The real objects that now reside where the group instance was before
        # should already be selected after duplicates_make_real.
        
        
        context.scene.objects.active = context.selected_objects[group_objects_count - 1]
        if debug:
            print(context.selected_objects, '\r\nactive_object: ', context.active_object)
        #Attention: Poll fails because a context of joining into an empty (as this is the active object) is not valid!
        if (not bpy.ops.object.join()):
            print('Joining the temporary selection (dupli group made real) failed.')
            #break
            
        
        x = context.active_object.dimensions[0]
        y = context.active_object.dimensions[1]
        z = context.active_object.dimensions[2]
        
        #now no longer required (copy instead of selected_object reference for recursion used now)
        #while --undo_count > 0:
        #    bpy.ops.ed.undo()
        bpy.ops.object.delete(use_global=False)#The duplicate should reside in this context's scene only!
        

    #measure
    unit = 'm'
    if (context.scene.unit_settings.system == 'IMPERIAL'):
        unit = 'ft'
    #determine units using the unit scale of the scene's unit/world settings
    dimensions = [
        str(round(x * context.scene.unit_settings.scale_length, context.scene.selection2actors_in_target_path)) + unit,
        str(round(y * context.scene.unit_settings.scale_length, context.scene.selection2actors_in_target_path)) + unit,
        str(round(z * context.scene.unit_settings.scale_length, context.scene.selection2actors_in_target_path)) + unit
    ]
    
    
    
    
    
    #undo - restore the modifiers #if no active object then no modifiers have been applied hence nothing to be undone.
    #if ( not (context.active_object is None) and not (result == {'CANCELLED'}) ):
    #    operations_undone_count = 0
    #    while (operations_undone_count < operations_to_undo_count): 
    #        result = bpy.ops.ed.undo()#undo_history()
    #        if (result):
    #            operations_undone_count = operations_undone_count + 1
    #    if debug:
    #        print('operations_undone count: ', operations_undone_count)
    
    whitespace_count = object_longest_label_len - len(entry)
    material_whitespace_count = material_longest_label_len - len(material)
    if debug:
        print('object whitespace count: ', whitespace_count, '\t material whitespace count: ', material_whitespace_count)
    bom_entry = '\t \t' + entry + getWhiteSpace(whitespace_count) + '\t \tMaterial: ' + material + getWhiteSpace(material_whitespace_count) + '\t \t[x:' + dimensions[0] + ',y:' + dimensions[1] + ',z:' + dimensions[2] + ']'
            #TODO take modifiers array, skin
            # and solidify into account (by e.g. applying all modifiers, examining and storing the dimensions and going
            #back in history to pre applying the modifiers!
            
            #NOT RELEVANT: + '\t \t[object is in group: ' o.users_group ', in Scenes: ' o.users_scene ']'
            
    return bom_entry






 

#
# White space for filling up to a certain length.
#
def getWhiteSpace(count):
    whitespace = ''
    for i in range(0, count - 1):
        whitespace = whitespace + ' '
    return whitespace





#
# All found bom entries are written to a file.
#
def write2file(filelink, object_actor_map):#<-- argument is a dictionary (key value pairs)!
    if debug:
        print('Writing 0AD actor file ...')
        
    if (filelink is None):
        filelink = build_filelink()
    if debug:
        print('Target filelink: ', filelink)
        
    #write to file
    result = False
    with open(filelink, 'w') as f:#for closing filestream automatically
        #f.read()
        #f.readhline()
        text = ''
        objects_treated = []
        for o, actor in object_actor_map.items():
            if not objects_treated.find(o):
                text = text + '\r\n' + o.name + ' ' + entry
            #text = text '\r\n'
            objects_treated.append(o)
            
        result = f.write(text)
        if (result):
            print('0AD actor file created: ', filelink)
        else :
            print('0AD actor file creation failed! ', filelink)
    return result
        
    

# This bom entry is appended to a file.
def append_bom_entry_to_file(context, bom_entry):
  return append_to_file(context, '\r\n' + str(bom_entry_count_map[bom_entry]) + 'x ' + bom_entry)
  
  
def append_to_file(context, content):
    
    if debug:
        print('Target filelink: ', filelink)
        
    #append to file
    with open(filelink, 'a') as f:#for closing filestream automatically
        #f.read()
        #f.readhline()
        if (f.write(content)):
            print('Appended to file: ', filelink, ' \t Content: ',  content)
            return True
        
        #f.tell()
        #f.seek(byte) #e.g. 0123 -> 4th byte is 3
        #http://docs.python.org/3/tutorial/inputoutput.html
    #f.close() -- no longer necessary when using with/scope
    #use pickle.dump(object, filestream) and pickle.load(filestream) (somewhat like serialization?)
    return False



def build_filelink(context):
    if debug:
        print('building filelink ...')

    #build filelink
    root = './'#using relative paths -> to home directory
    #root = os.getcwd()#<-- the directory of the current file (the question is of it's the blend file?)
    #root = dirname(pathname(__FILE__))#http://stackoverflow.com/questions/5137497/find-current-directory-and-files-directory
    filename = ''#TODO Determine this blender file name!
    fileending = '.xml'
    
    #objectname = getBaseName(context.selected_objects[0].name)
    objectname = context.scene.objects.active #context.active_object    
    objectname = context.scene.name
    if (not objectname or objectname is None):
        objectname = 'no-or-buggy-active-object'
    
    filename = filename + objectname
    filelink = root + filename + fileending
    
    #don't overwrite existing boms because for several selections individual boms
    # could be desired.
    number = 0
    while (os.path.isfile(filelink)):#alternatively: try: with (open(filelink)): ... except IOError: print('file not found') 
        number = number + 1              #http://stackoverflow.com/questions/82831/how-do-i-check-if-a-file-exists-using-python
        filename_ = filename + str(number)
        filelink = filename_ + fileending

    #A non-existant filelink for the bill of materials was found.
    return filelink






#HELPER - TIDYUPNAMES
def tidyUpNames():
    ############
    #fetch active object
    ############
    active_obj = isThereActiveObjectThenGet(context)
    if (not active_obj or active_obj is None):
        if debug:
            print('Aborting tidying up names because there is no active object.'
            ' So nothing was left after the joining or grouping?')
        return False
    ############
    #tidy up - dismiss the .001, .002, .. endings if necessary
    ############
    if debug:
        print('Object-name before refactoring: ', active_obj.name)
    cleanname = getBaseName(active_obj.name)
    if (cleanname and cleanname != active_obj.name):
        if debug:
            print('renaming')
        active_obj.name = cleanname
        if debug:
            print('renaming *done*')
    #debug
    if debug:
        print('Object-name after refactoring: ', active_obj.name)
    return True





#HELPER - ISTHERESELECTION
def isThereSelectionThenGet(context):
    #opt. check if selection only one object (as is to be expectat after join)
    sel = context.selected_objects
    if (debug):
        print('Count of objects in selection (hopefully 1): ', len(sel))
    if (sel is None or not sel):
        if debug:
            print('No selection! Is there nothing left by join action? *worried*',
            '\n\raborting renaming ...')
        return False
    #deliver the selection
    return sel





#HELPER - ISTHEREACTIVEOBJECT
def isThereActiveObjectThenGet(context):
    #get active object of context
    active_obj = context.active_object
    if (active_obj is None or not active_obj):
        if debug:
            print('No active object -',
            ' trying to make the first object of the selection the active one.')
        #check if selection and get
        sel = isThereSelectionThenGet(context)
        #make first object active (usually it should only be 1 object)
        context.scene.objects.active = sel[0]
    active_obj = context.active_object
    if (active_obj is None or not active_obj):
        if debug:
            print('Still no active object! Aborting renaming ...')
        return False
    #deliver the active object
    return active_obj





#HELPER - GETBASENAME
#@return string:basename aka cleanname
def getBaseName(s):
    obj_basename_parts = s.split('.')
    obj_basename_parts_L = len(obj_basename_parts)
    if debug:
        print('getBaseName: Last part: ', obj_basename_parts[obj_basename_parts_L - 1])
    if (obj_basename_parts_L > 1
    and re.match('[0-9]{3}$', obj_basename_parts[obj_basename_parts_L - 1])):
        if debug:
            print('getBaseName: determining base name')
        #attention: last item is left intentionally
        cleanname = ''
        for i in range(0, obj_basename_parts_L - 1):
            cleanname += obj_basename_parts[i]
        #done this strange way to avoid unnecessary GUI updates
        #as the sel.name fields in the UI may be unnecessarily updated on change ...
        if debug:
            print('getBaseName: determining *done*, determined basename: ', cleanname)
        return cleanname
    else:
        if debug:
            print('getBaseName: already tidied up *done*, basename: ', s)
        return s
    

#
#
#
def filterObjectsByRegex(list_with_object_references, regex):
    objects_in_filter = []
    for obj in list_with_object_references:
        if (obj and re.match(regex, obj.name)):
            objects_in_filter.append(obj)
    return objects_in_filter



#------- CLASSES --------------------------------------------------------------#


#
# JoinOrGroupMatchingObjects
#
# Wraps some general attributes and some specific ones
# like the actual content of the regex input field.
#                               inheritance
#
class OBJECT_OT_Selection2Actors(bpy.types.Operator):
    """Performs the operation (i.e. creating a set of related actor XML files) according to the settings."""
    #=======ATTRIBUTES=========================================================#
    bl_idname = "object.selection2actors"
    bl_label = "Create a Bill of Materials out of selected objects."
    " If no 'Material:<Material>' is given, the blender material is taken"
    " as the desired material. By default Group instances are resolved to"
    " their original group and from there to the therein contained objects"
    " - a group or instance thereof is no individual standalone part by default."
    " Application: Hide objects that shall be excluded from the BoM or select"
    " objects to be included in the BoM explicitely. If no selection is given"
    " then all the not hidden objects and groups are examined."
    bl_context = "objectmode"
    bl_register = True
    bl_undo = True
    #bl_options = {'REGISTER', 'UNDO'}
    
    #=======CONSTRUCTION=======================================================#
    #def __init__(self):
    #=======METHODS============================================================#
    @classmethod
    def poll(cls, context):#it's the same without self (always inserted before)
        #check the context
        #context does not matter here
        return True
        #The following condition no longer is required as auto-detection of mechanical objects is supported.
        #Also the following is not compatible with the possibility to either select objects for the bom
        #or hide objects that shall be exluded.
        #return context.selected_objects is not None && len(context.selected_objects) > 0

    def execute(self, context):
        main(context)
        return {'FINISHED'}





#
# GUI Panel
#
# Two or more inputs: 1x checkbox, 1x text input for the pattern.
# Extends Panel.
#
class VIEW3D_PT_tools_selection2actors(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_label = 'Export to 0AD Actors'
    bl_context = 'objectmode'
    bl_options = {'DEFAULT_CLOSED'}
    #DRAW
    def draw(self, context):
        s = context.scene
        in_mode_str = 'Objects'
        #get a string representation of enum button
        if debug:
            print('Mode: ', s.selection2actors_in_mode)
        layout = self.layout
        col = layout.column(align = True)
        col.row().prop(s, 'selection2actors_in_mode', expand = True)
        #splitbutton for enums (radio buttons) ...
        
        # textfield
        row = layout.row(align=True)
        row.prop(s, 'selection2actors_in_target_path')
        #row.active = (in_mode_str == 'Join')
        
        col = layout.column(align = True)
        col.label(text = 'Include hidden objects:')
        row = layout.row(align = True)
        row.prop(s, 'selection2actors_in_include_hidden')
            
        row = layout.row(align = True)
        label = in_mode_str + " to 0AD Actors!"
        if (s.selection2actors_in_mode != '0'):
            label = label + ' (derive parent objects first)'
        row.operator('object.selection2actors', icon='FILE_TICK', text = label)










#------- GENERAL BLENDER SETUP FUNCTIONS --------------------------------------#
# REGISTER
def register():
    bpy.utils.register_module(__name__)
    #bpy.utils.register_class(OBJECT_OT_Selection2Actors)
    #bpy.utils.register_class(VIEW3D_PT_tools_selection2actors)
    
    # mode
    bpy.types.Scene.selection2actors_in_mode = EnumProperty(
        name = "Mode",
        description = "Select whether to resolve parents "
                " underlaying group's contained objects or if a group"
                " is a standalone part on its own too.",
        items = [
            ("0", "Resolve parents", ""),
            ("1", "Only selection.", "")
        ],
        default='0'
    )
    # is hidden
    bpy.types.Scene.selection2actors_in_include_hidden = BoolProperty(
        name = "Include hidden objects?",
        description = "Whether to include hidden objects or not.",
        default = True
    )
    # output path
    bpy.types.Scene.selection2actors_in_target_path = TextProperty(
        name = "Path ",
        description = "target_path, i.e. digits after the comma. (e.g. 3 at default metric unit settings results in a resolution of .001m = 1mm.)"
        #,options = {'HIDDEN'}
        ,default = "."
    )
    #pass


#UNREGISTER
def unregister():
    bpy.utils.unregister_module(__name__)
    #bpy.utils.unregister_class(OBJECT_OT_Selection2Actors)
    #bpy.utils.unregister_class(VIEW3D_PT_tools_selection2actors)
    #please tidy up
    del bpy.types.Scene.selection2actors_in_mode
    del bpy.types.Scene.selection2actors_in_include_hidden
    del bpy.types.Scene.selection2actors_in_target_path
    #pass




class Actor():
    
    #class_var = ""
    
    def __init__(filelink, o, mesh_filelink):
        self.filelink = filelink
        self.mesh_filelink = mesh_filelink
        self.o = o
        self.groups = []
        

        
    def toXML():
        # override for sorted() order:
        Actor.__eq__ = lambda self, other: self.filelink == other.filelink
        Actor.__ne__ = lambda self, other: self.filelink != other.filelink
        Actor.__lt__ = lambda self, other: self.filelink < other.filelink
        Actor.__le__ = lambda self, other: self.filelink <= other.filelink
        Actor.__ge__ = lambda self, other: self.filelink >= other.filelink
        Actor.__gt__ = lambda self, other: self.filelink > other.filelink
        
        xml = '<?xml version="1.0" encoding="utf-8"?>'
        "\n"
        '<actor version="1">'
        for group in self.groups:
            xml = xml "\n" group.toXml()
        xml = xml '</actor>'
        return xml



class Group():
    
    def __init__():
        # Each group xml node contains at least one variant, which the engine picks 1 from randomly.
        self.variants = []
    
    def toXml():
        xml = "<group>\n"
        for variant in self.variants:
            xml = xml "\n" variant.toXml()
        xml = xml "\n  " '</group>' "\n"
        return xml



# TODO Pyrogenesis: If a variant name starts with winter_ or summer_ then choose depending on current season.
# Define one group with only one variant containing all default values (material, mesh, props, ...) and call it "Base" as only one can be picked. Order is important I think. Thus Base has to come first in the XML.
class Variant():
    
    # Define 
    def __init__():
        self.frequency = 100
        self.props = []
        
    def toXml():
        props_xml = ''
        for prop in self.props: #TODO use sorted(set(list)) to have a unique sorted sequence? Will objects be removed by set if the address is  equal? It is to be expected but is it certain?
            props_xml = props_xml "\n" prop.toXml()
            
        node_name = self.__class__.__name__.lower()
        return '<' node_name ' name="' self.actor_filelink_relative '" frequency="' self.frequency '">' props_xml '</' node_name '>'



class Prop():
    
    def __init__():
        # defaults:
        self.attachpoint = "root" # root is by convention the prop_point attached to the armature' root bone
        self.actor_filelink_relative = "optional_subfolder/actor.xml"
    
    def toXml():
        node_name = self.__class__.__name__.lower()
        return '<' node_name ' actor="' self.actor_filelink_relative '" attachpoint="' self.attachpoint '"></' node_name '>'
    




#------- PROCEDURAL -----------------------------------------------------------#
if __name__ == "__main__":
    #unregister()
    register()
    # test call
    #bpy.ops.io.export_to_0ad_actors()

