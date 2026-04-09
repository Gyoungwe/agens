# calculator

## 描述
Perform mathematical calculations

## 参数
- `expression` (string): Math expression [必需]

## 使用方式

```python
from skills.calculator.skill import CalculatorSkill

skill = CalculatorSkill()
result = await skill.execute('{"param1": "value1"}')
```

## 来源
claude_skill

## 版本
1.0.0
