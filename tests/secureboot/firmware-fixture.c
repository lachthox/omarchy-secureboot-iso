/* Native EFI acceptance fixture. This is not an Omarchy kernel or bootloader. */
#include <efi.h>
#include <efilib.h>

static void serial(const char *s) {
    while (*s) {
        unsigned char ready;
        do { __asm__ volatile("inb %1,%0" : "=a"(ready) : "Nd"((unsigned short)0x3fd)); } while (!(ready & 0x20));
        __asm__ volatile("outb %0,%1" :: "a"((unsigned char)*s++), "Nd"((unsigned short)0x3f8));
    }
}

static void shutdown(EFI_SYSTEM_TABLE *st) {
    uefi_call_wrapper(st->RuntimeServices->ResetSystem, 4, EfiResetShutdown, EFI_SUCCESS, 0, NULL);
}

EFI_STATUS efi_main(EFI_HANDLE handle, EFI_SYSTEM_TABLE *st) {
    InitializeLib(handle, st);
    EFI_GUID global = EFI_GLOBAL_VARIABLE;
    UINT8 sb = 0, setup = 1;
    UINTN size = 1;
    EFI_STATUS status = uefi_call_wrapper(st->RuntimeServices->GetVariable, 5, L"SecureBoot", &global, NULL, &size, &sb);
    size = 1;
    status |= uefi_call_wrapper(st->RuntimeServices->GetVariable, 5, L"SetupMode", &global, NULL, &size, &setup);
    if (EFI_ERROR(status) || sb != 1 || setup != 0) {
        serial("FIRMWARE_POLICY_NOT_ENFORCING\n"); shutdown(st); return EFI_SECURITY_VIOLATION;
    }
    serial("FIRMWARE_SECUREBOOT_1_SETUPMODE_0\n");
#ifdef PAYLOAD
    serial("VERIFIED_PAYLOAD_EXECUTED\n");
    shutdown(st);
    return EFI_SUCCESS;
#else
    EFI_LOADED_IMAGE *loaded = NULL;
    status = uefi_call_wrapper(st->BootServices->HandleProtocol, 3, handle, &LoadedImageProtocol, (void **)&loaded);
    if (EFI_ERROR(status)) { serial("LOADER_PROTOCOL_FAILED\n"); shutdown(st); return status; }
    CHAR16 *paths[] = { L"\\EFI\\Linux\\omarchy-current.efi", L"\\EFI\\Linux\\omarchy-recovery.efi" };
    for (UINTN i = 0; i < 2; ++i) {
        EFI_DEVICE_PATH *dp = FileDevicePath(loaded->DeviceHandle, paths[i]);
        EFI_HANDLE child = NULL;
        status = uefi_call_wrapper(st->BootServices->LoadImage, 6, FALSE, handle, dp, NULL, 0, &child);
        if (status == EFI_SECURITY_VIOLATION || status == EFI_ACCESS_DENIED) {
            serial(i == 0 ? "FIRMWARE_REJECTED_CURRENT\n" : "FIRMWARE_REJECTED_RECOVERY\n");
            continue;
        }
        if (EFI_ERROR(status)) {
            serial(i == 0 ? "CURRENT_NOT_LOADABLE\n" : "RECOVERY_NOT_LOADABLE\n");
            continue;
        }
        serial(i == 0 ? "STARTING_VERIFIED_CURRENT\n" : "STARTING_VERIFIED_RECOVERY\n");
        uefi_call_wrapper(st->BootServices->StartImage, 3, child, NULL, NULL);
    }
    serial("NO_VERIFIED_BOOT_IMAGE\n"); shutdown(st); return EFI_SECURITY_VIOLATION;
#endif
}
