#[[
    Arieo Package Manager - CMake Module
    
    Provides ARIEO_WORKSPACE() function for managing packages with
    environment variables and remote/local package sources.
    
    Usage:
        ARIEO_WORKSPACE(
            ENVIRONMENT_VARIABLES
                VAR_NAME=set:value
                VAR_NAME=append:value
                VAR_NAME=prepend:value
            ARIEO_PACKAGES
                REMOTE
                    https://github.com/user/repo.git@branch
                LOCAL
                    /path/to/local/package
        )
]]
cmake_minimum_required(VERSION 4.2.3) 

include(${CMAKE_CURRENT_LIST_DIR}/package/arieo_remote_package.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/package/arieo_local_package.cmake)

function(ARIEO_WORKSPACE)
    set(oneValueArgs
    )
    set(multiValueArgs 
        ENVIRONMENT_VARIABLES
        STAGES
    )

    cmake_parse_arguments(
        ARGUMENT
        ""
        "${oneValueArgs}"
        "${multiValueArgs}"
        ${ARGN}
    )

    if(DEFINED ARGUMENT_ENVIRONMENT_VARIABLES)
        apply_environments(${ARGUMENT_ENVIRONMENT_VARIABLES})
    endif()

    if (NOT DEFINED ENV{ARIEO_WORKSPACE_ROOT_DIR})
        message(FATAL_ERROR "Environment variable ARIEO_WORKSPACE_ROOT_DIR is not defined.")
    endif()

    if (NOT DEFINED ENV{ARIEO_PACKAGES_INSTALL_DIR})
        message(FATAL_ERROR "Environment variable ARIEO_PACKAGES_INSTALL_DIR is not defined.")
    endif()    

    set(CMAKE_INSTALL_PREFIX $ENV{ARIEO_PACKAGES_INSTALL_DIR} CACHE PATH "Installation directory for Arieo packages" FORCE)

    project(ArieoWorkspace)
    if(DEFINED ARGUMENT_STAGES)
        message(STATUS "[arieo_workspace] Processing stages: ${ARGUMENT_STAGES}")
        add_stages("${ARGUMENT_STAGES}")
    endif()
endfunction()

function(apply_environments environments)
    # Process environment variable settings
    foreach(env_var IN LISTS ARGUMENT_ENVIRONMENT_VARIABLES)
        string(REGEX MATCH "^([A-Za-z_][A-Za-z0-9_]*)=(set|append|prepend):(.+)$" _match "${env_var}")
        if(_match)
            set(var_name "${CMAKE_MATCH_1}")
            set(operation "${CMAKE_MATCH_2}")
            set(value "${CMAKE_MATCH_3}")
            
            if(operation STREQUAL "set")
                set(ENV{${var_name}} "${value}" CACHE STRING "Environment variable ${var_name}")
            elseif(operation STREQUAL "append")
                if(DEFINED ENV{${var_name}})
                    set(ENV{${var_name}} "$ENV{${var_name}};${value}" CACHE STRING "Environment variable ${var_name}")
                else()
                    set(ENV{${var_name}} "${value}" CACHE STRING "Environment variable ${var_name}")
                endif()
            elseif(operation STREQUAL "prepend")
                if(DEFINED ENV{${var_name}})
                    set(ENV{${var_name}} "${value};$ENV{${var_name}}" CACHE STRING "Environment variable ${var_name}")
                else()
                    set(ENV{${var_name}} "${value}" CACHE STRING "Environment variable ${var_name}")
                endif()
            endif()
            
            message(STATUS "[arieo_workspace] ${operation} ${var_name}=$ENV{${var_name}}")
        endif()
    endforeach()
endfunction()

function(add_stages)
    set(oneValueArgs
    )
    set(multiValueArgs 
        INSTALL_BUILD_ENV_STAGE
        INSTALL_THIRD_PARTIES_STAGE
        BUILD_ENGINE_STAGE
        BUILD_APPLICATION_STAGE
    )
    cmake_parse_arguments(
        ARGUMENT
        ""
        "${oneValueArgs}"
        "${multiValueArgs}"
        ${ARGN}
    )

    if(DEFINED ARGUMENT_INSTALL_BUILD_ENV_STAGE)
        if("${ARIEO_BUILD_CONFIGURE_STAGE}" STREQUAL "INSTALL_BUILD_ENV_STAGE")
            add_single_stage("${ARGUMENT_INSTALL_BUILD_ENV_STAGE}")
        endif()
    endif()

    if(DEFINED ARGUMENT_INSTALL_THIRD_PARTIES_STAGE)
        if("${ARIEO_BUILD_CONFIGURE_STAGE}" STREQUAL "INSTALL_THIRD_PARTIES_STAGE")
            add_single_stage("${ARGUMENT_INSTALL_THIRD_PARTIES_STAGE}")
        endif()
    endif()

    if(DEFINED ARGUMENT_BUILD_ENGINE_STAGE)
        if("${ARIEO_BUILD_CONFIGURE_STAGE}" STREQUAL "BUILD_ENGINE_STAGE")
            add_single_stage("${ARGUMENT_BUILD_ENGINE_STAGE}")
        endif()
    endif()

    if(DEFINED ARGUMENT_BUILD_APPLICATION_STAGE)
        if("${ARIEO_BUILD_CONFIGURE_STAGE}" STREQUAL "BUILD_APPLICATION_STAGE")
            add_single_stage("${ARGUMENT_BUILD_APPLICATION_STAGE}")
        endif()
    endif()
endfunction()

function(add_single_stage)
    set(oneValueArgs
    )
    set(multiValueArgs 
        PACKAGES
    )
    cmake_parse_arguments(
        ARGUMENT
        ""
        "${oneValueArgs}"
        "${multiValueArgs}"
        ${ARGN}
    )

    message(STATUS "[arieo_workspace] Processing stage: ${parameters}")

    if(DEFINED ARGUMENT_PACKAGES)
        add_stage_packages("${ARGUMENT_PACKAGES}")
    endif()
endfunction()
        
function(add_stage_packages)
    set(oneValueArgs
    )
    set(multiValueArgs 
        LOCAL
        REMOTE
    )
    cmake_parse_arguments(
        ARGUMENT
        ""
        "${oneValueArgs}"
        "${multiValueArgs}"
        ${ARGN}
    )

    if(DEFINED ARGUMENT_REMOTE)
        # Process remote packages first to ensure they are available for local packages that may depend on them
        foreach(remote_pkg IN LISTS ARGUMENT_REMOTE)
            message(STATUS "Remote package specified: ${remote_pkg}")
            #split repo and tag from remote_pkg in format repo_url@tag
            string(REGEX MATCH "(.+)@(.+)" _match "${remote_pkg}")
            if(_match)
                set(repo_url "${CMAKE_MATCH_1}")
                set(repo_tag "${CMAKE_MATCH_2}")
            else()
                message(FATAL_ERROR "Invalid remote package format: ${remote_pkg}. Expected format: <git_url>@<branch_or_tag>")
            endif()
            
            arieo_add_remote_package(
                GIT_REPOSITORY ${repo_url}
                GIT_TAG ${repo_tag}
            )                
        endforeach()
    endif()

    # Process local packages after remote packages to allow local packages to depend on remote ones
    if(DEFINED ARGUMENT_LOCAL)
        foreach(local_pkg_path IN LISTS ARGUMENT_LOCAL)
            message(STATUS "Local package specified: ${local_pkg_path}")

            arieo_add_local_package(
                LOCAL_PACKAGE_PATH ${local_pkg_path}
            )
        endforeach()
    endif()
endfunction()