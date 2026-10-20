file(GLOB_RECURSE app_sources ${CMAKE_SOURCE_DIR}/src/*.cpp ${CMAKE_SOURCE_DIR}/src/*.c)
# Migration firmware has its own entry point and is built by its existing
# Arduino profiles. It must never enter the staging application component.
list(FILTER app_sources EXCLUDE REGEX "/migration/")
idf_component_register(SRCS ${app_sources})
