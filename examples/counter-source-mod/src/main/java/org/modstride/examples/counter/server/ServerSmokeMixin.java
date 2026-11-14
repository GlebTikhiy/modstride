package org.modstride.examples.counter.server;

import java.util.function.BooleanSupplier;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.dedicated.DedicatedServer;
import org.modstride.examples.counter.FieldCounter;
import org.slf4j.LoggerFactory;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(MinecraftServer.class)
abstract class ServerSmokeMixin {
    @Inject(method = "tickServer", at = @At("TAIL"))
    private void modstride$checkServer(BooleanSupplier hasTimeLeft, CallbackInfo callback) {
        if (!Boolean.getBoolean("modstride.counter.serverSmoke")) {
            return;
        }
        MinecraftServer server = (MinecraftServer) (Object) this;
        if (!(server instanceof DedicatedServer)) {
            return;
        }
        if (!(BuiltInRegistries.ITEM.get(new ResourceLocation("modstride_counter", "field_counter"))
                instanceof FieldCounter)) {
            throw new IllegalStateException("Field Counter failed to register");
        }
        LoggerFactory.getLogger("modstride-counter").info("MODSTRIDE_COUNTER_SERVER_READY");
        server.halt(false);
    }
}
