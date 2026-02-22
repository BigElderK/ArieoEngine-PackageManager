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
        
function(add_stage_packages package_links)

    # ── Phase 1: parse all links, build URL→path map, sync remotes ──────────
    # Also build base_url→full_url map to detect tag conflicts later.
    # base_url = URL with @tag stripped (e.g. https://github.com/.../Repo.git)
    set(all_paths "")
    set(seen_urls "")
    set(tag_conflict_errors "")
    set(dup_url_errors "")
    foreach(package_link IN LISTS package_links)
        parsing_pakage_link_string("${package_link}" type url local_path)

        # If no local path was provided, derive it from the URL:
        # $ENV{ARIEO_PACKAGES_DEFAULT_REMOTE_SOURCE_DIR}/<PackageName>-<Tag>
        if(NOT local_path)
            string(REGEX REPLACE "@[^@/]+$" "" base_url_for_name "${url}")
            string(REGEX MATCH "[^/]+$" pkg_name "${base_url_for_name}")
            string(REGEX REPLACE "\\.git$" "" pkg_name "${pkg_name}")
            string(REGEX MATCH "@([^@/]+)$" tag_match "${url}")
            set(pkg_tag "${CMAKE_MATCH_1}")
            if(NOT pkg_tag)
                message(FATAL_ERROR "[arieo_workspace] Cannot derive local path for '${url}': no @tag specified. Either add a tag (e.g. @main) or provide an explicit path with '=>'.")
            endif()
            set(local_path "$ENV{ARIEO_PACKAGES_DEFAULT_REMOTE_SOURCE_DIR}/${pkg_name}-${pkg_tag}")
            message(STATUS "[arieo_workspace] No path specified for ${url}, derived: ${local_path}")
        endif()

        # Strip @tag to get base URL for conflict detection
        string(REGEX REPLACE "@[^@/]+$" "" base_url "${url}")
        string(MD5 base_hash "${base_url}")

        get_property(existing_url GLOBAL PROPERTY "ARIEO_PKG_BASEURL_${base_hash}")
        if(existing_url AND NOT existing_url STREQUAL url)
            string(APPEND tag_conflict_errors
                "  STAGE PACKAGE TAG CONFLICT:\n"
                "    base URL : ${base_url}\n"
                "    first tag: ${existing_url}\n"
                "    new tag  : ${url}\n"
            )
        else()
            set_property(GLOBAL PROPERTY "ARIEO_PKG_BASEURL_${base_hash}" "${url}")
        endif()

        # Detect duplicate URLs within this stage
        if(url IN_LIST seen_urls)
            string(APPEND dup_url_errors "  DUPLICATE URL in stage: ${url}\n")
        else()
            list(APPEND seen_urls "${url}")
        endif()

        string(MD5 url_hash "${url}")
        set_property(GLOBAL PROPERTY "ARIEO_PKG_PATH_${url_hash}" "${local_path}")
        list(APPEND all_paths "${local_path}")

        if(type STREQUAL "REMOTE")
            sync_remote_package("${url}" "${local_path}")
        endif()
    endforeach()

    if(dup_url_errors)
        message(FATAL_ERROR "[arieo_workspace] Duplicate URL(s) in stage package list:\n${dup_url_errors}")
    endif()

    if(tag_conflict_errors)
        message(FATAL_ERROR "[arieo_workspace] Tag conflict(s) in stage package list:\n${tag_conflict_errors}")
    endif()

    # ── Phase 2: read DEPENDS, validate tags, store dep lists ────────────────
    set(dep_tag_conflict_errors "")
    set(dep_missing_errors "")
    foreach(path IN LISTS all_paths)
        get_package_info("${path}" deps)
        string(MD5 path_hash "${path}")
        set_property(GLOBAL PROPERTY "ARIEO_PKG_DEPS_${path_hash}" "${deps}")
        message(STATUS "[arieo_workspace] ${path} depends on: ${deps}")

        foreach(dep_url IN LISTS deps)
            # Check if this dep references a known base URL with a different tag
            string(REGEX REPLACE "@[^@/]+$" "" dep_base_url "${dep_url}")
            string(MD5 dep_base_hash "${dep_base_url}")
            get_property(registered_url GLOBAL PROPERTY "ARIEO_PKG_BASEURL_${dep_base_hash}")
            if(registered_url AND NOT registered_url STREQUAL dep_url)
                string(APPEND dep_tag_conflict_errors
                    "  DEPENDS TAG CONFLICT in ${path}:\n"
                    "    dep URL          : ${dep_url}\n"
                    "    registered as    : ${registered_url}\n"
                )
            elseif(NOT registered_url)
                string(APPEND dep_missing_errors
                    "  MISSING DEPENDS in ${path}:\n"
                    "    dep URL : ${dep_url}\n"
                    "    This package is not listed in the current stage's PACKAGES.\n"
                    "    Add it as:  \"REMOTE: ${dep_url} => <local_path>\"\n"
                    "             or \"LOCAL:  ${dep_url} => <local_path>\"\n"
                )
            endif()
        endforeach()
    endforeach()

    if(dep_missing_errors)
        message(FATAL_ERROR "[arieo_workspace] Missing package(s) in stage:\n${dep_missing_errors}")
    endif()

    if(dep_tag_conflict_errors)
        message(FATAL_ERROR "[arieo_workspace] DEPENDS tag conflict(s) detected:\n${dep_tag_conflict_errors}")
    endif()

    # ── Phase 3: Kahn's topological sort ─────────────────────────────────────
    # Init in-degree = 0 for every package
    foreach(path IN LISTS all_paths)
        string(MD5 h "${path}")
        set_property(GLOBAL PROPERTY "ARIEO_TOPO_INDEG_${h}" 0)
    endforeach()

    # For each package A: for each dep-URL of A that resolves to a known path → A.in-degree++
    foreach(path IN LISTS all_paths)
        string(MD5 h "${path}")
        get_property(deps GLOBAL PROPERTY "ARIEO_PKG_DEPS_${h}")
        foreach(dep_url IN LISTS deps)
            string(MD5 dep_url_hash "${dep_url}")
            get_property(dep_path GLOBAL PROPERTY "ARIEO_PKG_PATH_${dep_url_hash}")
            if(dep_path)
                get_property(cur_indeg GLOBAL PROPERTY "ARIEO_TOPO_INDEG_${h}")
                math(EXPR new_indeg "${cur_indeg} + 1")
                set_property(GLOBAL PROPERTY "ARIEO_TOPO_INDEG_${h}" ${new_indeg})
            endif()
        endforeach()
    endforeach()

    # Seed queue with all zero-in-degree packages
    set(queue "")
    foreach(path IN LISTS all_paths)
        string(MD5 h "${path}")
        get_property(indeg GLOBAL PROPERTY "ARIEO_TOPO_INDEG_${h}")
        if(indeg EQUAL 0)
            list(APPEND queue "${path}")
        endif()
    endforeach()

    # BFS: pop a package, append to sorted list, decrement dependents' in-degrees
    set(sorted_paths "")
    while(queue)
        list(POP_FRONT queue cur_path)
        list(APPEND sorted_paths "${cur_path}")

        # Find every package that lists cur_path as a dependency and decrement it
        foreach(path IN LISTS all_paths)
            string(MD5 h "${path}")
            get_property(deps GLOBAL PROPERTY "ARIEO_PKG_DEPS_${h}")
            foreach(dep_url IN LISTS deps)
                string(MD5 dep_url_hash "${dep_url}")
                get_property(dep_path GLOBAL PROPERTY "ARIEO_PKG_PATH_${dep_url_hash}")
                if(dep_path STREQUAL cur_path)
                    get_property(cur_indeg GLOBAL PROPERTY "ARIEO_TOPO_INDEG_${h}")
                    math(EXPR new_indeg "${cur_indeg} - 1")
                    set_property(GLOBAL PROPERTY "ARIEO_TOPO_INDEG_${h}" ${new_indeg})
                    if(new_indeg EQUAL 0)
                        list(APPEND queue "${path}")
                    endif()
                    break()  # count each dependency edge only once
                endif()
            endforeach()
        endforeach()
    endwhile()

    # Cycle detection
    list(LENGTH sorted_paths sorted_count)
    list(LENGTH all_paths    total_count)
    if(NOT sorted_count EQUAL total_count)
        set(cycle_msg "[arieo_workspace] Circular dependency detected!\n")
        string(APPEND cycle_msg "  Packages involved in cycle(s):\n")
        foreach(path IN LISTS all_paths)
            list(FIND sorted_paths "${path}" found_idx)
            if(found_idx EQUAL -1)
                string(MD5 h "${path}")
                get_property(remaining_indeg GLOBAL PROPERTY "ARIEO_TOPO_INDEG_${h}")
                get_property(deps GLOBAL PROPERTY "ARIEO_PKG_DEPS_${h}")
                string(APPEND cycle_msg "    PACKAGE: ${path}  (unresolved in-degree: ${remaining_indeg})\n")
                foreach(dep_url IN LISTS deps)
                    string(MD5 dep_url_hash "${dep_url}")
                    get_property(dep_path GLOBAL PROPERTY "ARIEO_PKG_PATH_${dep_url_hash}")
                    list(FIND sorted_paths "${dep_path}" dep_found_idx)
                    if(dep_found_idx EQUAL -1)
                        if(dep_path)
                            string(APPEND cycle_msg "      -> UNRESOLVED DEP: ${dep_url}\n")
                            string(APPEND cycle_msg "                   path: ${dep_path}\n")
                        else()
                            string(APPEND cycle_msg "      -> EXTERNAL DEP (not in stage): ${dep_url}\n")
                        endif()
                    endif()
                endforeach()
            endif()
        endforeach()
        message(FATAL_ERROR "${cycle_msg}")
    endif()

    # Add subdirectories in build order
    message(STATUS "[arieo_workspace] Build order:")
    set(idx 0)
    foreach(path IN LISTS sorted_paths)
        math(EXPR idx "${idx} + 1")
        message(STATUS "[arieo_workspace]   ${idx}. ${path}")
        add_subdirectory("${path}")
    endforeach()

    # message(FATAL_ERROR "WOKAO")
endfunction()

function (parsing_pakage_link_string package_link out_type out_url out_local_path)
    # Try format with "=>" mapping first: "TYPE: <url> => <path>"
    string(REGEX MATCH "^(REMOTE|LOCAL):[ \t]*([^ \t=>][^=]*)[ \t]*=>[ \t]*(.+)$" _match "${package_link}")
    if(_match)
        set(${out_type} "${CMAKE_MATCH_1}" PARENT_SCOPE)
        string(STRIP "${CMAKE_MATCH_2}" _stripped_url)
        set(${out_url} "${_stripped_url}" PARENT_SCOPE)
        string(STRIP "${CMAKE_MATCH_3}" _stripped_path)
        set(${out_local_path} "${_stripped_path}" PARENT_SCOPE)
        return()
    endif()
    # Try format without "=>" mapping: "TYPE: <url>"
    string(REGEX MATCH "^(REMOTE|LOCAL):[ \t]*(.+)$" _match "${package_link}")
    if(_match)
        set(${out_type} "${CMAKE_MATCH_1}" PARENT_SCOPE)
        string(STRIP "${CMAKE_MATCH_2}" _stripped_url)
        set(${out_url} "${_stripped_url}" PARENT_SCOPE)
        set(${out_local_path} "" PARENT_SCOPE)
        return()
    endif()
    message(FATAL_ERROR "Invalid package link format: ${package_link}. Expected format: [REMOTE|LOCAL]: <git_url>@<branch_or_tag> => <local_path>")
endfunction()

function (get_package_info cmake_dir out_depends_list)
    file(READ "${cmake_dir}/CMakeLists.txt" _cmake_content)

    # Extract the ARIEO_PACKAGE(...) block (content up to first closing paren)
    string(REGEX MATCH "ARIEO_PACKAGE[ \t\r\n]*\\(([^)]*)" _match "${_cmake_content}")
    set(_package_block "${CMAKE_MATCH_1}")

    # Extract everything after the DEPENDS keyword (multiline safe: no .* regex)
    set(_depends_list "")
    string(FIND "${_package_block}" "DEPENDS" _depends_pos)
    if(NOT _depends_pos EQUAL -1)
        string(LENGTH "DEPENDS" _depends_kw_len)
        math(EXPR _after_depends "${_depends_pos} + ${_depends_kw_len}")
        string(SUBSTRING "${_package_block}" ${_after_depends} -1 _depends_raw)
        # Tokenize by any whitespace/newlines
        string(REGEX REPLACE "[ \t\r\n]+" ";" _depends_tokens "${_depends_raw}")
        foreach(_token IN LISTS _depends_tokens)
            string(STRIP "${_token}" _token)
            # Stop when we hit another known keyword
            if(_token MATCHES "^(CATEGORY|COMPONENTS|URL)$")
                break()
            endif()
            if(_token)
                list(APPEND _depends_list "${_token}")
            endif()
        endforeach()
    endif()

    set(${out_depends_list} "${_depends_list}" PARENT_SCOPE)
endfunction()

function (sync_remote_package package_url local_dir)
    # Split "https://...Repo.git@tag" into git_url and branch
    string(REGEX MATCH "@([^@/]+)$" tag_match "${package_url}")
    set(git_tag "${CMAKE_MATCH_1}")
    string(REGEX REPLACE "@[^@/]+$" "" git_url "${package_url}")

    if(NOT git_tag)
        message(FATAL_ERROR "[arieo_workspace] sync_remote_package: no @tag in URL '${package_url}'")
    endif()

    if(NOT EXISTS ${local_dir})
        execute_process(
            COMMAND git clone --branch ${git_tag} --depth 1 ${git_url} ${local_dir}
            RESULT_VARIABLE clone_result
        )
        if(NOT clone_result EQUAL 0)
            message(FATAL_ERROR "[arieo_workspace] git clone failed for ${git_url} (branch: ${git_tag}) to ${local_dir}")
        endif()
    else()
        execute_process(
            COMMAND git -C ${local_dir} pull
            RESULT_VARIABLE pull_result
        )
        if(NOT pull_result EQUAL 0)
            message(WARNING "[arieo_workspace] git pull failed for ${local_dir}")
        endif()
    endif()
endfunction()