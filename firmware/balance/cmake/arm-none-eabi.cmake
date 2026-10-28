# Toolchain file: the GNU Arm Embedded toolchain (arm-none-eabi-gcc) for the STM32G474RE (Cortex-M4F).
# The compiler is taken from ARM_TOOLCHAIN_DIR (its bin/ or the directory itself) when set, else from PATH
# (CI: Ubuntu's gcc-arm-none-eabi; locally the Arm GNU Toolchain tarball).
set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

set(ARM_TOOLCHAIN_DIR "$ENV{ARM_TOOLCHAIN_DIR}" CACHE PATH "Arm GNU toolchain root (empty: PATH)")
set(_hint "")
if(ARM_TOOLCHAIN_DIR)
    set(_hint HINTS "${ARM_TOOLCHAIN_DIR}/bin" "${ARM_TOOLCHAIN_DIR}" NO_DEFAULT_PATH)
endif()
find_program(ARM_GCC arm-none-eabi-gcc ${_hint} REQUIRED)
get_filename_component(_bin "${ARM_GCC}" DIRECTORY)

set(CMAKE_C_COMPILER "${_bin}/arm-none-eabi-gcc")
set(CMAKE_ASM_COMPILER "${_bin}/arm-none-eabi-gcc")
set(CMAKE_OBJCOPY "${_bin}/arm-none-eabi-objcopy" CACHE FILEPATH "")
set(CMAKE_SIZE "${_bin}/arm-none-eabi-size" CACHE FILEPATH "")

set(GP_MCU_FLAGS "-mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard")
set(CMAKE_C_FLAGS_INIT "${GP_MCU_FLAGS} -ffunction-sections -fdata-sections -fno-common")
set(CMAKE_ASM_FLAGS_INIT "${GP_MCU_FLAGS} -x assembler-with-cpp")
set(CMAKE_EXE_LINKER_FLAGS_INIT "${GP_MCU_FLAGS} --specs=nano.specs --specs=nosys.specs -Wl,--gc-sections")

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
