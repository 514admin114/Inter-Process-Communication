cmake_minimum_required(VERSION 3.10)
project(IPC_Performance_Test_CPP)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Platform-specific settings
if(WIN32)
    add_definitions(-D_WIN32_WINNT=0x0600)
endif()

# Main executable
add_executable(ipc_test_cpp main.cpp)

# Include directories
target_include_directories(ipc_test_cpp PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

# Platform-specific libraries
if(WIN32)
    target_link_libraries(ipc_test_cpp ws2_32)
endif()

# Set output directory
set_target_properties(ipc_test_cpp PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
)
