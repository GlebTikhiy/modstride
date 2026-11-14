package org.modstride.examples.counter.client;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.TitleScreen;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import org.modstride.examples.counter.FieldCounter;
import org.slf4j.LoggerFactory;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(Minecraft.class)
abstract class ClientSmokeMixin {
    @Inject(method = "tick", at = @At("TAIL"))
    private void modstride$checkTitleScreen(CallbackInfo callback) {
        if (!Boolean.getBoolean("modstride.counter.smoke")) {
            return;
        }
        Minecraft client = (Minecraft) (Object) this;
        if (!(client.screen instanceof TitleScreen) || client.getOverlay() != null) {
            return;
        }
        if (!(BuiltInRegistries.ITEM.get(new ResourceLocation("modstride_counter", "field_counter"))
                instanceof FieldCounter)) {
            throw new IllegalStateException("Field Counter failed to register");
        }
        LoggerFactory.getLogger("modstride-counter").info("MODSTRIDE_COUNTER_CLIENT_READY");
        client.stop();
    }
}
