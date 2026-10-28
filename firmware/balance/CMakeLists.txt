# Gyropup balance firmware (D63): the Nucleo-G474RE image, or on the host the control core's library and tests.
#
#   cmake -S firmware/balance -B build/fw-mcu -DCMAKE_TOOLCHAIN_FILE=firmware/balance/cmake/arm-none-eabi.cmake
#   cmake --build build/fw-mcu                    # balance.elf / .bin / .hex, the sizes printed
#   cmake -S firmware/balance -B build/fw-host && cmake --build build/fw-host && ctest --test-dir build/fw-host
cmake_minimum_required(VERSION 3.22)
project(gyropup_balance LANGUAGES C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

set(GP_CORE_SOURCES
    src/core/gp_app.c
    src/core/gp_control.c
    src/core/gp_fivebar.c
    src/core/gp_ina228.c
    src/core/gp_jetson.c
    src/core/gp_rs04.c
    src/core/gp_vesc.c
    src/core/gp_vn100.c)
set(GP_WARNINGS -Wall -Wextra -Wshadow -Wdouble-promotion -Wno-unused-parameter)

if(CMAKE_CROSSCOMPILING)
    include(cmake/stm32g4.cmake)
else()
    # ---------------------------------------------------------------- host: the core as a library, its tests
    add_library(gp_core STATIC ${GP_CORE_SOURCES})
    target_include_directories(gp_core PUBLIC include)
    target_compile_options(gp_core PRIVATE ${GP_WARNINGS} -Werror)
    set_target_properties(gp_core PROPERTIES POSITION_INDEPENDENT_CODE ON)
    target_link_libraries(gp_core PUBLIC m)

    # the HIL's library (hil/fwlib.py loads it with ctypes)
    add_library(gp_host SHARED src/host/gp_host.c)
    target_link_libraries(gp_host PRIVATE gp_core)
    target_compile_options(gp_host PRIVATE ${GP_WARNINGS} -Werror)

    enable_testing()
    add_executable(test_core tests/test_core.c tests/test_platform.c)
    target_link_libraries(test_core PRIVATE gp_core)
    target_compile_options(test_core PRIVATE ${GP_WARNINGS})
    add_test(NAME core COMMAND test_core)
endif()
