# test_calculator

## 描述
A test calculator skill

## 参数
- `expression` (string): Math expression [必需]

## 使用方式

```python
from skills.test_calculator.skill import TestCalculatorSkill

skill = TestCalculatorSkill()
result = await skill.execute('{"param1": "value1"}')
```

## 来源
claude_skill

## 版本
1.0.0
