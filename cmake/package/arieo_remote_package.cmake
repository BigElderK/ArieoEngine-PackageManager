#[[
    Arieo Remote Package - CMake Module
    
    Usage:
        arieo_add_remote_package(
            NAME            <package_name>
            GIT_REPOSITORY  <git_url>
            GIT_TAG         <branch_or_tag>
            SOURCE_DIR      <source_directory>
            BINARY_DIR      <binary_directory>
        )
]]

include(ExternalProject)

cmake_minimum_required(VERSION 3.11)

include(FetchContent)

function(arieo_add_remote_package)
    cmake_parse_arguments(ARG 
        ""
        "GIT_REPOSITORY;GIT_TAG;" 
        "" 
        ${ARGN}
    )

    # Get package name from git repository URL (last part of URL, strip .git if present)
    string(REGEX MATCH ".*/([^/]+)$" _match "${ARG_GIT_REPOSITORY}")
    if(_match)
        set(package_name "${CMAKE_MATCH_1}")
        string(REGEX REPLACE "\\.git$" "" package_name "${package_name}")
    else()
        message(FATAL_ERROR "Could not extract package name from git repository URL: ${ARG_GIT_REPOSITORY}")
    endif()
    message(STATUS "Adding remote package: 
        GIT_REPOSITORY=${ARG_GIT_REPOSITORY}
        GIT_TAG=${ARG_GIT_TAG}
        SOURCE_DIR=$ENV{ARIEO_PACKAGES_REMOTE_SOURCE_DIR}/${package_name}
        BINARY_DIR=$ENV{ARIEO_PACKAGES_BUILD_OUTPUT_DIR}/${package_name}
        INSTALL_DIR=$ENV{ARIEO_PACKAGES_INSTALL_DIR}/${package_name}
    ")

    # If SOURCE_DIR does not exist, call git clone to SOURCE_DIR, otherwise update it with git pull
    set(source_dir $ENV{ARIEO_PACKAGES_REMOTE_SOURCE_DIR}/${package_name})
    if(NOT EXISTS ${source_dir})
        execute_process(
            COMMAND git clone --branch ${ARG_GIT_TAG} --depth 1 ${ARG_GIT_REPOSITORY} ${source_dir}
            RESULT_VARIABLE clone_result
        )
        if(NOT clone_result EQUAL 0)
            message(FATAL_ERROR "git clone failed for ${ARG_GIT_REPOSITORY} to ${source_dir}")
        endif()
    else()
        execute_process(
            COMMAND git -C ${source_dir} pull
            RESULT_VARIABLE pull_result
        )
        if(NOT pull_result EQUAL 0)
            message(WARNING "git pull failed for ${source_dir}")
        endif()
    endif()

    # check if there is a CMakeLists.txt in the source dir
    if(NOT EXISTS "${source_dir}/CMakeLists.txt")
        message(FATAL_ERROR "Local package source directory ${source_dir} does not contain a CMakeLists.txt file.")
    endif()

    add_subdirectory(
        ${source_dir}
    )
endfunction()


