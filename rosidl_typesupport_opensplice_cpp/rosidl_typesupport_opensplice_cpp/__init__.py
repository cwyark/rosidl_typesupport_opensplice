# Copyright 2014-2018 Open Source Robotics Foundation, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import subprocess

from rosidl_cmake import generate_files

from .convert_to_opensplice_idl import convert_to_opensplice_idl


def generate_dds_opensplice_cpp(
    pkg_name, dds_interface_files, deps, opensplice_idl_output_path, output_basepath, idl_pp
):
    include_dirs = []
    for dep in deps:
        # only take the first : for separation, as Windows follows with a C:\
        dep_parts = dep.split(':', 1)
        assert len(dep_parts) == 2, "The dependency '%s' must contain a double colon" % dep
        idl_path = dep_parts[1]
        idl_base_path = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.normpath(idl_path))))
        if idl_base_path not in include_dirs:
            include_dirs.append(idl_base_path)
    if 'OSPL_TMPL_PATH' in os.environ:
        include_dirs.append(os.environ['OSPL_TMPL_PATH'])

    # Ensure output directory for converted IDL files exists
    try:
        os.makedirs(opensplice_idl_output_path)
    except FileExistsError:
        pass

    # Convert IDL files for OpenSplice compatibility
    for idl_file in dds_interface_files:
        assert os.path.exists(idl_file), 'Could not find IDL file: ' + idl_file
        convert_to_opensplice_idl(idl_file, opensplice_idl_output_path)


    for idl_file in dds_interface_files:
        parent_folder = os.path.dirname(idl_file)
        output_path = os.path.join(
            output_basepath,
            os.path.basename(parent_folder),
            'dds_opensplice')
        try:
            os.makedirs(output_path)
        except FileExistsError:
            pass

        # idlpp doesn't like long path arguments over 256 chars, get just the filename
        filename = os.path.basename(idl_file)

        cmd = [idl_pp]
        for include_dir in include_dirs:
            cmd += ['-I', include_dir]
        cmd += [
            '-S',
            '-l', 'cpp',
            '-N',
            '-d', output_path,
            filename
        ]
        if os.name == 'nt':
            cmd[-1:-1] = [
                '-P',
                'ROSIDL_TYPESUPPORT_OPENSPLICE_CPP_PUBLIC_%s,%s' % (
                    pkg_name,
                    '%s/msg/rosidl_typesupport_opensplice_cpp__visibility_control.h' % pkg_name)]

        subprocess.check_call(cmd, cwd=opensplice_idl_output_path)

        # modify generated code to
        # remove path information of the building machine as well as timestamps
        msg_name = os.path.splitext(filename)[0]
        idl_path = os.path.join(
            pkg_name, os.path.basename(parent_folder), filename)
        h_filename = os.path.join(output_path, '%s.h' % msg_name)
        _modify(h_filename, msg_name, _replace_path_and_timestamp, idl_path=idl_path)
        cpp_filename = os.path.join(output_path, '%s.cpp' % msg_name)
        _modify(cpp_filename, msg_name, _replace_path_and_timestamp, idl_path=idl_path)
        dcps_h_filename = os.path.join(output_path, '%sDcps.h' % msg_name)
        _modify(dcps_h_filename, msg_name, _replace_path_and_timestamp, idl_path=idl_path)
        dcps_cpp_filename = os.path.join(output_path, '%sDcps.cpp' % msg_name)
        _modify(dcps_cpp_filename, msg_name, _replace_path_and_timestamp, idl_path=idl_path)

    return 0


def _modify(filename, msg_name, callback, idl_path=None):
    with open(filename, 'r') as h:
        lines = h.read().split('\n')
    modified = callback(lines, msg_name, idl_path=idl_path)
    if modified:
        with open(filename, 'w') as h:
            h.write('\n'.join(lines))


def _replace_path_and_timestamp(lines, msg_name, idl_path):
    found_source = False
    for i, line in enumerate(lines):
        if line.startswith('//  Source: '):
            assert not found_source, "More than one '// Source: ' line was found"
            found_source = True
            lines[i] = '//  Source: ' + idl_path
            continue
        if line.startswith('//  Generated: '):
            assert found_source, "No '// Source: ' line was found before"
            lines[i] = '//  Generated: timestamp removed to make the build reproducible'
            break
    else:
        assert False, "Failed to find '// Generated: ' line"
    return lines


def generate_typesupport_opensplice_cpp(arguments_file):
    mapping = {
       'idl__rosidl_typesupport_opensplice_cpp.hpp.em':  # noqa
           '%s__rosidl_typesupport_opensplice_cpp.hpp',
       'idl__dds_opensplice__type_support.cpp.em': 'dds_opensplice/%s__type_support.cpp',
    }

    generate_files(arguments_file, mapping)
