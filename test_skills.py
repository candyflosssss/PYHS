#!/usr/bin/env python3
"""
测试技能系统功能
"""

import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_skills():
    """测试技能系统功能"""
    try:
        print("正在测试技能系统...")
        
        # 测试导入
        from systems.skill_strategy import get_skill, list_available_skills
        print("✅ 技能策略系统导入成功")
        
        # 测试可用技能列表
        print("✅ 测试可用技能列表...")
        skills = list_available_skills()
        print(f"  可用技能数量: {len(skills)}")
        for i, skill in enumerate(skills, 1):
            print(f"  {i}. {skill}")
        
        # 测试获取特定技能
        print("✅ 测试获取特定技能...")
        test_skills = ['sweep', 'basic_heal', 'drain', 'taunt', 'arcane_missiles', 'power_slam', 'destiny']
        for skill_name in test_skills:
            skill = get_skill(skill_name)
            if skill:
                print(f"  ✅ {skill_name}: {skill}")
            else:
                print(f"  ❌ {skill_name}: 未找到")
        
        # 测试技能执行（模拟）
        print("✅ 测试技能执行...")
        sweep_skill = get_skill('sweep')
        if sweep_skill:
            print(f"  横扫技能: {sweep_skill}")
            print(f"  技能名称: {sweep_skill.name}")
            print(f"  技能描述: {sweep_skill.description}")
            print(f"  体力消耗: {sweep_skill.stamina_cost}")
        else:
            print("  ❌ 横扫技能未找到")
        
        print("\n🎉 技能系统测试完成！")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_skills()
