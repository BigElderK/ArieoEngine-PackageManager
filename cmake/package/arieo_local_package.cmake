
function(arieo_add_local_package)
    cmake_parse_arguments(ARG "" "LOCAL_PACKAGE_PATH" "" ${ARGN})

    message(STATUS "Adding local package: 
        PACKAGE_PATH=${LOCAL_PACKAGE_PATH}
    ")

    # check if there is a CMakeLists.txt in the source dir
    if(NOT EXISTS "${ARG_LOCAL_PACKAGE_PATH}/CMakeLists.txt")
        message(FATAL_ERROR "Local package source directory ${ARG_LOCAL_PACKAGE_PATH} does not contain a CMakeLists.txt file.")
    endif()

    add_subdirectory(
        ${ARG_LOCAL_PACKAGE_PATH}
    )
    # include ("${ARG_LOCAL_PACKAGE_PATH}/CMakeLists.txt")
endfunction()
