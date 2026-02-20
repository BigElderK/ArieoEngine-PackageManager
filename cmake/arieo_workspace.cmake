#[[
    Arieo Package Manager - CMake Module
    
    Provides arieo_package_manager() function for managing packages with
    environment variables and remote/local package sources.
    
    Usage:
        arieo_package_manager(
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

function(arieo_workspace)
    set(oneValueArgs
    )
    set(multiValueArgs 
        ENVIRONMENT_VARIABLES
        ARIEO_PACKAGES
    )

    cmake_parse_arguments(
        ARGUMENT
        ""
        "${oneValueArgs}"
        "${multiValueArgs}"
        ${ARGN}
    )

    project(ArieoWorkspace)

    # Process environment variable settings
    foreach(env_var IN LISTS ARGUMENT_ENVIRONMENT_VARIABLES)
        string(REGEX MATCH "^([A-Za-z_][A-Za-z0-9_]*)=(set|append|prepend):(.+)$" _match "${env_var}")
        if(_match)
            set(var_name "${CMAKE_MATCH_1}")
            set(operation "${CMAKE_MATCH_2}")
            set(value "${CMAKE_MATCH_3}")
            
            if(operation STREQUAL "set")
                set(ENV{${var_name}} "${value}")
            elseif(operation STREQUAL "append")
                if(DEFINED ENV{${var_name}})
                    set(ENV{${var_name}} "$ENV{${var_name}};${value}")
                else()
                    set(ENV{${var_name}} "${value}")
                endif()
            elseif(operation STREQUAL "prepend")
                if(DEFINED ENV{${var_name}})
                    set(ENV{${var_name}} "${value};$ENV{${var_name}}")
                else()
                    set(ENV{${var_name}} "${value}")
                endif()
            endif()
            
            message(STATUS "[arieo_workspace] ${operation} ${var_name}=$ENV{${var_name}}")
        endif()
    endforeach()

    if(DEFINED ARGUMENT_ARIEO_PACKAGES)
        cmake_parse_arguments(
            ARGUMENT_ARIEO_PACKAGES
            ""
            ""
            "LOCAL;REMOTE"
            ${ARGUMENT_ARIEO_PACKAGES}
        )

        if(DEFINED ARGUMENT_ARIEO_PACKAGES_REMOTE)
            # Process remote packages first to ensure they are available for local packages that may depend on them
            foreach(remote_pkg IN LISTS ARGUMENT_ARIEO_PACKAGES_REMOTE)
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
        if(DEFINED ARGUMENT_ARIEO_PACKAGES_LOCAL)
            foreach(local_pkg_path IN LISTS ARGUMENT_ARIEO_PACKAGES_LOCAL)
                message(STATUS "Local package specified: ${local_pkg_path}")

                arieo_add_local_package(
                    LOCAL_PACKAGE_PATH ${local_pkg_path}
                )
            endforeach()
        endif()
        
    endif()
endfunction()


