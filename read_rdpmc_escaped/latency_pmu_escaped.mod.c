#include <linux/module.h>
#define INCLUDE_VERMAGIC
#include <linux/build-salt.h>
#include <linux/vermagic.h>
#include <linux/compiler.h>

BUILD_SALT;

MODULE_INFO(vermagic, VERMAGIC_STRING);
MODULE_INFO(name, KBUILD_MODNAME);

__visible struct module __this_module
__section(".gnu.linkonce.this_module") = {
	.name = KBUILD_MODNAME,
	.init = init_module,
#ifdef CONFIG_MODULE_UNLOAD
	.exit = cleanup_module,
#endif
	.arch = MODULE_ARCH_INIT,
};

#ifdef CONFIG_RETPOLINE
MODULE_INFO(retpoline, "Y");
#endif

static const struct modversion_info ____versions[]
__used __section("__versions") = {
	{ 0xbbbaf8e8, "module_layout" },
	{ 0x49c1b58b, "param_ops_int" },
	{ 0x6d23fc67, "param_array_ops" },
	{ 0x37a0cba, "kfree" },
	{ 0x6228c21f, "smp_call_function_single" },
	{ 0x740a1b95, "reserve_evntsel_nmi" },
	{ 0xd7dd777b, "reserve_perfctr_nmi" },
	{ 0xeb233a45, "__kmalloc" },
	{ 0xa648e561, "__ubsan_handle_shift_out_of_bounds" },
	{ 0xc5850110, "printk" },
	{ 0x71871c39, "pv_ops" },
	{ 0x7a2af7b4, "cpu_number" },
	{ 0x5a5a2271, "__cpu_online_mask" },
	{ 0x63c4d61f, "__bitmap_weight" },
	{ 0x9e683f75, "__cpu_possible_mask" },
	{ 0x17de3d5, "nr_cpu_ids" },
	{ 0x4d8c750, "release_perfctr_nmi" },
	{ 0xa70fabbe, "release_evntsel_nmi" },
	{ 0xb3258f79, "__ubsan_handle_type_mismatch_v1" },
	{ 0x54b1fac6, "__ubsan_handle_load_invalid_value" },
	{ 0x87a21cb3, "__ubsan_handle_out_of_bounds" },
	{ 0xbdfb6dbb, "__fentry__" },
};

MODULE_INFO(depends, "");


MODULE_INFO(srcversion, "3FD62EC875D78EA24CCAB89");
