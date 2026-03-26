cmake_minimum_required(VERSION 3.14)
project(math_benchmark CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Try system Eigen first (brew install eigen)
find_package(Eigen3 3.3 NO_MODULE QUIET)

if(NOT Eigen3_FOUND)
    # Fallback: search common Homebrew / system include paths
    find_path(EIGEN3_INCLUDE_DIR "Eigen/Dense"
        PATHS
            /opt/homebrew/include/eigen3
            /usr/local/include/eigen3
            /usr/include/eigen3
            /opt/local/include/eigen3
    )
    if(EIGEN3_INCLUDE_DIR)
        message(STATUS "Found Eigen headers at ${EIGEN3_INCLUDE_DIR}")
        add_library(Eigen3::Eigen INTERFACE IMPORTED)
        target_include_directories(Eigen3::Eigen INTERFACE ${EIGEN3_INCLUDE_DIR})
    else()
        message(STATUS "Eigen not found locally — fetching via FetchContent")
        include(FetchContent)
        FetchContent_Declare(
            Eigen
            URL https://gitlab.com/libeigen/eigen/-/archive/3.4.0/eigen-3.4.0.tar.gz
            URL_HASH SHA256=8586084f71f9bde545ee7fa6d00288b264a2b7ac3607b974e54d13e7162c1c72
        )
        set(EIGEN_BUILD_DOC OFF CACHE BOOL "" FORCE)
        set(BUILD_TESTING OFF CACHE BOOL "" FORCE)
        FetchContent_MakeAvailable(Eigen)
    endif()
endif()

add_executable(benchmark benchmark.cpp)
target_link_libraries(benchmark PRIVATE Eigen3::Eigen)
target_compile_options(benchmark PRIVATE -O3 -march=native)
