"""Apply only to a clean, exact Hyperspace 1.20.0 checkout. Does not build/install DLLs."""
from pathlib import Path
import subprocess,shutil,sys
PIN='2540d807baef1d3654ff03a18560728b64ce3a45'
def install(root):
    root=Path(root).resolve()
    commit=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
    if commit!=PIN:raise SystemExit('Refusing: expected exact Hyperspace v1.20.0 commit '+PIN)
    if subprocess.check_output(['git','-C',str(root),'status','--porcelain'],text=True).strip():
        raise SystemExit('Refusing: checkout must be clean; preserve your existing changes first.')
    lua=root/'lua/LuaScriptInit.cpp';cmake=root/'CMakeLists.txt'
    text=lua.read_text()
    needle='    removeDangerousStuff(lua);'
    if text.count(needle)!=1:raise SystemExit('Unexpected Lua initialization source')
    text=text.replace('#include "LuaScriptInit.h"','#include "LuaScriptInit.h"\n#include "../fleet_native/fleet_native_api.h"',1)
    text=text.replace(needle,needle+'\n    fleet_register_transport(lua);',1)
    dst=root/'fleet_native';dst.mkdir()
    for name in ('fleet_native_api.h','fleet_native_api.cpp','fleet_transport.hpp','fleet_transport.cpp','fleet_video.cpp','fleet_pixels.hpp','fleet_combat.cpp','fleet_gl_view.hpp','fleet_scene.cpp','fleet_scene_codec.hpp','fleet_effects.cpp','fleet_boarding.cpp','fleet_boarding.hpp'):
        shutil.copyfile(Path(__file__).parent/name,dst/name)
    lua.write_text(text)
    renderer=root/'Renderer.cpp'
    renderer.write_text(renderer.read_text().replace('if (argv.find("-opengl") != std::string::npos)', 'if (argv.find("-opengl") != std::string::npos && argv.find("--force-opengl") == std::string::npos)'))
    with cmake.open('a') as f:
        f.write('\n# Fleet transport/view and opt-in enemy-replica freeze; no third ship.\ntarget_sources(Hyperspace PRIVATE fleet_native/fleet_transport.cpp fleet_native/fleet_native_api.cpp fleet_native/fleet_video.cpp fleet_native/fleet_combat.cpp fleet_native/fleet_scene.cpp fleet_native/fleet_effects.cpp fleet_native/fleet_boarding.cpp)\nif(WIN32)\n    target_link_libraries(Hyperspace PRIVATE ws2_32)\nendif()\n')
    print('Applied native local-transport extension to pinned source. DLL is not built.')
if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: python install_patch.py PATH_TO_CLEAN_HYPERSPACE_1_20_0')
    install(sys.argv[1])
