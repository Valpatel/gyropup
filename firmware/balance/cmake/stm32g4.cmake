# The Nucleo-G474RE image: the STM32G4 HAL, the CMSIS device and CMSIS core fetched at configure time from
# STMicroelectronics' GitHub at the tags STM32CubeG4 v1.6.3 pins (HAL v1.2.7, device v1.2.6, CMSIS 5.6.0), each archive
# checked against its SHA-256. Nothing of ST's is kept in this repository; the HAL's configuration header is written
# into the build tree from ST's template with only the modules this firmware uses.
enable_language(ASM)
include(FetchContent)

# the core's flags on every target whatever CMAKE_C_FLAGS says (the toolchain file's *_INIT flags are only defaults)
separate_arguments(_mcu UNIX_COMMAND "${GP_MCU_FLAGS}")
add_compile_options(${_mcu})
add_link_options(${_mcu})

FetchContent_Declare(st_hal
    URL https://github.com/STMicroelectronics/stm32g4xx_hal_driver/archive/refs/tags/v1.2.7.tar.gz
    URL_HASH SHA256=a1129cebc41e1edda1ba81cd3a43d91fcc8b508a1c318cde9f9f136aba50909f
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
FetchContent_Declare(st_cmsis_device
    URL https://github.com/STMicroelectronics/cmsis_device_g4/archive/refs/tags/v1.2.6.tar.gz
    URL_HASH SHA256=a150d4b334610d8d8445385e9104d08aa7ae8c4e443b2a7dc6f19c9711d8bb4c
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
FetchContent_Declare(st_cmsis_core
    URL https://github.com/STMicroelectronics/cmsis_core/archive/refs/tags/v5.6.0_cm4.tar.gz
    URL_HASH SHA256=9259ec0c97a0b2e7cd3c09a7625a896804ce7391a2d915c70bba0ca975731300
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
foreach(dep st_hal st_cmsis_device st_cmsis_core)
    FetchContent_GetProperties(${dep})
    if(NOT ${dep}_POPULATED)
        FetchContent_Populate(${dep})
    endif()
endforeach()

# ---------------------------------------------------------------- the HAL's configuration, from ST's template
set(GP_HAL_MODULES CORTEX DMA EXTI FDCAN FLASH GPIO I2C IWDG PWR RCC TIM UART)
file(READ "${st_hal_SOURCE_DIR}/Inc/stm32g4xx_hal_conf_template.h" _conf)
string(REGEX REPLACE "#define HAL_([A-Z0-9]+)_MODULE_ENABLED" "/* #define HAL_\\1_MODULE_ENABLED */" _conf "${_conf}")
string(REPLACE "/* #define HAL_MODULE_ENABLED */" "#define HAL_MODULE_ENABLED" _conf "${_conf}")
foreach(m ${GP_HAL_MODULES})
    string(REPLACE "/* #define HAL_${m}_MODULE_ENABLED */" "#define HAL_${m}_MODULE_ENABLED" _conf "${_conf}")
endforeach()
string(REPLACE "#define HSE_VALUE    (8000000UL)" "#define HSE_VALUE    (24000000UL)" _conf "${_conf}") # the Nucleo's X3
set(GP_GEN "${CMAKE_BINARY_DIR}/generated")
file(WRITE "${GP_GEN}/stm32g4xx_hal_conf.h.new" "${_conf}")
configure_file("${GP_GEN}/stm32g4xx_hal_conf.h.new" "${GP_GEN}/stm32g4xx_hal_conf.h" COPYONLY)

# ---------------------------------------------------------------- the HAL as a library
set(GP_HAL_SOURCES "${st_hal_SOURCE_DIR}/Src/stm32g4xx_hal.c")
foreach(m cortex dma dma_ex exti fdcan flash flash_ex gpio i2c i2c_ex iwdg pwr pwr_ex rcc rcc_ex tim tim_ex uart uart_ex)
    list(APPEND GP_HAL_SOURCES "${st_hal_SOURCE_DIR}/Src/stm32g4xx_hal_${m}.c")
endforeach()
add_library(st_hal STATIC ${GP_HAL_SOURCES} "${st_cmsis_device_SOURCE_DIR}/Source/Templates/system_stm32g4xx.c")
target_include_directories(st_hal PUBLIC
    "${GP_GEN}"
    "${st_hal_SOURCE_DIR}/Inc"
    "${st_cmsis_device_SOURCE_DIR}/Include"
    "${st_cmsis_core_SOURCE_DIR}/Core/Include")
target_compile_definitions(st_hal PUBLIC STM32G474xx USE_HAL_DRIVER)
target_compile_options(st_hal PRIVATE -Wno-unused-parameter)

# ---------------------------------------------------------------- the firmware
add_executable(balance.elf
    ${GP_CORE_SOURCES}
    src/mcu/main.c
    src/mcu/board.c
    src/mcu/stm32g4xx_it.c
    src/mcu/syscalls.c
    "${st_cmsis_device_SOURCE_DIR}/Source/Templates/gcc/startup_stm32g474xx.s")
target_include_directories(balance.elf PRIVATE include src/mcu)
target_link_libraries(balance.elf PRIVATE st_hal m)
target_compile_options(balance.elf PRIVATE $<$<COMPILE_LANGUAGE:C>:${GP_WARNINGS} -Werror>)
set(GP_PROFILE "robot" CACHE STRING "robot | rig: the firmware's default profile")
if(GP_PROFILE STREQUAL "rig")
    target_compile_definitions(balance.elf PRIVATE GP_DEFAULT_PROFILE=1)
endif()
set(GP_SHUNT "fuse_board" CACHE STRING "fuse_board (1 mOhm, P3) | blue_sea (0.333 mOhm, P0-P2): the INA228's shunt")
if(GP_SHUNT STREQUAL "blue_sea")
    target_compile_definitions(balance.elf PRIVATE GP_SHUNT_OHM=0.000333f)
endif()
target_link_options(balance.elf PRIVATE
    -T${CMAKE_CURRENT_SOURCE_DIR}/src/mcu/STM32G474RETX_FLASH.ld
    -Wl,-Map=${CMAKE_BINARY_DIR}/balance.map -Wl,--print-memory-usage
    $<$<VERSION_GREATER_EQUAL:${CMAKE_C_COMPILER_VERSION},12>:-Wl,--no-warn-rwx-segments>)
set_target_properties(balance.elf PROPERTIES LINK_DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/src/mcu/STM32G474RETX_FLASH.ld)
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "" FORCE)
endif()
set(CMAKE_C_FLAGS_RELEASE "-O2 -g")
add_custom_command(TARGET balance.elf POST_BUILD
    COMMAND ${CMAKE_OBJCOPY} -O binary balance.elf balance.bin
    COMMAND ${CMAKE_OBJCOPY} -O ihex balance.elf balance.hex
    COMMAND ${CMAKE_SIZE} --format=berkeley balance.elf
    COMMENT "balance.bin, balance.hex")
