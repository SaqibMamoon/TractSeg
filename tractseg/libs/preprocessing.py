
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
from os.path import join
from pkg_resources import resource_filename

from tractseg.libs import img_utils


def move_to_MNI_space(input_file, bvals, bvecs, brain_mask, output_dir):
    print("Moving input to MNI space...")

    os.system("calc_FA -i " + input_file + " -o " + output_dir + "/FA.nii.gz --bvals " + bvals +
              " --bvecs " + bvecs + " --brain_mask " + brain_mask)

    dwi_spacing = img_utils.get_image_spacing(input_file)

    template_path = resource_filename('resources', 'MNI_FA_template.nii.gz')

    os.system("flirt -ref " + template_path + " -in " + output_dir + "/FA.nii.gz -out " + output_dir +
              "/FA_MNI.nii.gz -omat " + output_dir + "/FA_2_MNI.mat -dof 6 -cost mutualinfo -searchcost mutualinfo")

    os.system("flirt -ref " + template_path + " -in " + input_file + " -out " + output_dir +
              "/Diffusion_MNI.nii.gz -applyisoxfm " + dwi_spacing + " -init " + output_dir + "/FA_2_MNI.mat -dof 6")
    os.system("cp " + bvals + " " + output_dir + "/Diffusion_MNI.bvals")
    os.system("rotate_bvecs -i " + bvecs + " -t " + output_dir + "/FA_2_MNI.mat" +
              " -o " + output_dir + "/Diffusion_MNI.bvecs")

    new_input_file = join(output_dir, "Diffusion_MNI.nii.gz")
    bvecs = join(output_dir, "Diffusion_MNI.bvecs")
    bvals = join(output_dir, "Diffusion_MNI.bvals")

    brain_mask = create_brain_mask(new_input_file, output_dir)

    return new_input_file, bvals, bvecs, brain_mask


def move_to_subject_space(output_dir):
    print("Moving input to subject space...")

    file_path_in = output_dir + "/bundle_segmentations.nii.gz"
    file_path_out = output_dir + "/bundle_segmentations_subjectSpace.nii.gz"
    dwi_spacing = img_utils.get_image_spacing(file_path_in)
    os.system("convert_xfm -omat " + output_dir + "/MNI_2_FA.mat -inverse " + output_dir + "/FA_2_MNI.mat")
    os.system("flirt -ref " + output_dir + "/FA.nii.gz -in " + file_path_in + " -out " + file_path_out +
              " -applyisoxfm " + dwi_spacing + " -init " + output_dir + "/MNI_2_FA.mat -dof 6")
    os.system("fslmaths " + file_path_out + " -thr 0.5 -bin " + file_path_out)


def create_brain_mask(input_file, output_dir):
    print("Creating brain mask...")

    os.system("export PATH=/usr/local/fsl/bin:$PATH")

    input_dir = os.path.dirname(input_file)
    input_file_without_ending = os.path.basename(input_file).split(".")[0]
    os.system("bet " + join(input_dir, input_file_without_ending) + " " +
              output_dir + "/nodif_brain_mask.nii.gz  -f 0.3 -g 0 -m")
    os.system("rm " + output_dir + "/nodif_brain_mask.nii.gz")  # masked brain
    os.system("mv " + output_dir + "/nodif_brain_mask_mask.nii.gz " + output_dir + "/nodif_brain_mask.nii.gz")
    return join(output_dir, "nodif_brain_mask.nii.gz")


def create_fods(input_file, output_dir, bvals, bvecs, brain_mask, csd_type, nr_cpus=-1):
    os.system("export PATH=/code/mrtrix3/bin:$PATH")

    if nr_cpus > 0:
        nthreads = " -nthreads " + str(nr_cpus)
    else:
        nthreads = ""

    if csd_type == "csd_msmt_5tt":
        # MSMT 5TT
        print("Creating peaks (1 of 4)...")
        t1_file = join(os.path.dirname(input_file), "T1w_acpc_dc_restore_brain.nii.gz")
        os.system("5ttgen fsl " + t1_file + " " + output_dir + "/5TT.nii.gz -premasked" + nthreads)
        print("Creating peaks (2 of 4)...")
        os.system("dwi2response msmt_5tt " + input_file + " " + output_dir + "/5TT.nii.gz " + output_dir +
                  "/RF_WM.txt " + output_dir + "/RF_GM.txt " + output_dir + "/RF_CSF.txt -voxels " + output_dir +
                  "/RF_voxels.nii.gz -fslgrad " + bvecs + " " + bvals + " -mask " + brain_mask + nthreads)
        print("Creating peaks (3 of 4)...")
        os.system("dwi2fod msmt_csd " + input_file + " " + output_dir + "/RF_WM.txt " + output_dir +
                  "/WM_FODs.nii.gz " + output_dir + "/RF_GM.txt " + output_dir + "/GM.nii.gz " + output_dir +
                  "/RF_CSF.txt " + output_dir + "/CSF.nii.gz -mask " + brain_mask +
                  " -fslgrad " + bvecs + " " + bvals + nthreads)  # multi-shell, multi-tissue
        print("Creating peaks (4 of 4)...")
        os.system("sh2peaks " + output_dir + "/WM_FODs.nii.gz " + output_dir + "/peaks.nii.gz -quiet" + nthreads)
    elif csd_type == "csd_msmt":
        # MSMT DHollander    (only works with msmt_csd, not with csd)
        # (Dhollander does not need a T1 image to estimate the response function)
        print("Creating peaks (1 of 3)...")
        os.system("dwi2response dhollander -mask " + brain_mask + " " + input_file + " " + output_dir + "/RF_WM.txt " +
                  output_dir + "/RF_GM.txt " + output_dir + "/RF_CSF.txt -fslgrad " + bvecs + " " + bvals +
                  " -mask " + brain_mask + nthreads)
        print("Creating peaks (2 of 3)...")
        os.system("dwi2fod msmt_csd " + input_file + " " +
                  output_dir + "/RF_WM.txt " + output_dir + "/WM_FODs.nii.gz " +
                  output_dir + "/RF_GM.txt " + output_dir + "/GM_FODs.nii.gz " +
                  output_dir + "/RF_CSF.txt " + output_dir + "/CSF_FODs.nii.gz " +
                  "-fslgrad " + bvecs + " " + bvals + " -mask " + brain_mask + nthreads)
        print("Creating peaks (3 of 3)...")
        os.system("sh2peaks " + output_dir + "/WM_FODs.nii.gz " + output_dir + "/peaks.nii.gz -quiet" + nthreads)
    elif csd_type == "csd":
        # CSD Tournier
        print("Creating peaks (1 of 3)...")
        os.system("dwi2response tournier " + input_file + " " + output_dir + "/response.txt -mask " + brain_mask +
                  " -fslgrad " + bvecs + " " + bvals + " -quiet" + nthreads)
        print("Creating peaks (2 of 3)...")
        os.system("dwi2fod csd " + input_file + " " + output_dir + "/response.txt " + output_dir +
                  "/WM_FODs.nii.gz -mask " + brain_mask + " -fslgrad " + bvecs + " " + bvals + " -quiet" + nthreads)
        print("Creating peaks (3 of 3)...")
        os.system("sh2peaks " + output_dir + "/WM_FODs.nii.gz " + output_dir + "/peaks.nii.gz -quiet" + nthreads)
    else:
        raise ValueError("'csd_type' contains invalid String")


def clean_up(keep_intermediate_files, predict_img_output, csd_type, preprocessing_done=False):
    if not keep_intermediate_files:
        os.chdir(predict_img_output)

        # os.system("rm -f nodif_brain_mask.nii.gz")
        # os.system("rm -f peaks.nii.gz")
        os.system("rm -f WM_FODs.nii.gz")

        if csd_type == "csd_msmt" or csd_type == "csd_msmt_5tt":
            os.system("rm -f 5TT.nii.gz")
            os.system("rm -f RF_WM.txt")
            os.system("rm -f RF_GM.txt")
            os.system("rm -f RF_CSF.txt")
            os.system("rm -f RF_voxels.nii.gz")
            os.system("rm -f CSF.nii.gz")
            os.system("rm -f GM.nii.gz")
            os.system("rm -f CSF_FODs.nii.gz")
            os.system("rm -f GM_FODs.nii.gz")
        else:
            os.system("rm -f response.txt")

    if preprocessing_done:
        os.system("rm -f FA.nii.gz")
        os.system("rm -f FA_MNI.nii.gz")
        os.system("rm -f FA_2_MNI.mat")
