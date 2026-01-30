#!/bin/bash

# Script de Validación del Proyecto Unity
# Verifica que todos los archivos necesarios estén presentes

echo "🔍 VALIDANDO PROYECTO UNITY - Juego de Linterna"
echo "================================================"
echo ""

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0
WARNINGS=0

# Función para verificar archivo
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✅${NC} $1"
        return 0
    else
        echo -e "${RED}❌${NC} $1 - NO ENCONTRADO"
        ((ERRORS++))
        return 1
    fi
}

# Función para verificar directorio
check_dir() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✅${NC} $1/"
        return 0
    else
        echo -e "${YELLOW}⚠️${NC} $1/ - NO ENCONTRADO"
        ((WARNINGS++))
        return 1
    fi
}

echo "📁 ESTRUCTURA DE CARPETAS"
echo "-------------------------"
check_dir "Assets"
check_dir "Assets/Scripts"
check_dir "Assets/Scenes"
check_dir "ProjectSettings"
check_dir "Packages"
echo ""

echo "📝 SCRIPTS PRINCIPALES"
echo "----------------------"
check_file "Assets/Scripts/FirstPersonController.cs"
check_file "Assets/Scripts/FlashlightController.cs"
check_file "Assets/Scripts/BatterySystem.cs"
check_file "Assets/Scripts/BatteryPickup.cs"
check_file "Assets/Scripts/InteractionSystem.cs"
check_file "Assets/Scripts/IInteractable.cs"
check_file "Assets/Scripts/BatteryUI.cs"
check_file "Assets/Scripts/GameManager.cs"
echo ""

echo "⚙️ CONFIGURACIÓN"
echo "----------------"
check_file "Assets/PlayerInputActions.inputactions"
check_file "Packages/manifest.json"
check_file "README.md"
echo ""

echo "🔍 VERIFICANDO DEPENDENCIAS EN manifest.json"
echo "---------------------------------------------"
if [ -f "Packages/manifest.json" ]; then
    if grep -q "com.unity.inputsystem" Packages/manifest.json; then
        echo -e "${GREEN}✅${NC} Input System encontrado"
    else
        echo -e "${RED}❌${NC} Input System NO encontrado en manifest.json"
        ((ERRORS++))
    fi

    if grep -q "com.unity.textmeshpro" Packages/manifest.json; then
        echo -e "${GREEN}✅${NC} TextMeshPro encontrado"
    else
        echo -e "${YELLOW}⚠️${NC} TextMeshPro NO encontrado en manifest.json"
        ((WARNINGS++))
    fi

    if grep -q "com.unity.ugui" Packages/manifest.json; then
        echo -e "${GREEN}✅${NC} Unity UI (uGUI) encontrado"
    else
        echo -e "${YELLOW}⚠️${NC} Unity UI NO encontrado en manifest.json"
        ((WARNINGS++))
    fi
fi
echo ""

echo "🔎 ANÁLISIS DE CÓDIGO"
echo "---------------------"

# Verificar que no haya errores comunes de sintaxis
if [ -f "Assets/Scripts/FirstPersonController.cs" ]; then
    if grep -q "using UnityEngine.InputSystem;" Assets/Scripts/FirstPersonController.cs; then
        echo -e "${GREEN}✅${NC} FirstPersonController usa Input System"
    else
        echo -e "${RED}❌${NC} FirstPersonController NO usa Input System"
        ((ERRORS++))
    fi
fi

if [ -f "Assets/Scripts/BatterySystem.cs" ]; then
    if grep -q "UnityEvent" Assets/Scripts/BatterySystem.cs; then
        echo -e "${GREEN}✅${NC} BatterySystem usa UnityEvents"
    else
        echo -e "${YELLOW}⚠️${NC} BatterySystem podría no usar eventos"
        ((WARNINGS++))
    fi
fi

echo ""
echo "📊 ESTADÍSTICAS"
echo "---------------"
total_cs=$(find Assets/Scripts -name "*.cs" 2>/dev/null | wc -l)
total_lines=$(find Assets/Scripts -name "*.cs" -exec wc -l {} + 2>/dev/null | tail -1 | awk '{print $1}')
echo "Scripts de C#: $total_cs"
echo "Líneas totales: $total_lines"
echo ""

echo "================================================"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ VALIDACIÓN EXITOSA${NC}"
    echo "El proyecto está listo para abrirse en Unity!"
else
    echo -e "${RED}❌ ENCONTRADOS $ERRORS ERRORES${NC}"
    echo "Revisa los archivos faltantes antes de abrir en Unity"
fi

if [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}⚠️ $WARNINGS advertencias (no críticas)${NC}"
fi

echo ""
echo "📖 Para más información, lee:"
echo "   - README.md"
echo "   - VALIDATION_REPORT.md"
echo ""

exit $ERRORS
