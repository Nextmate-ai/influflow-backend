def get_config_value(value):
    """
    辅助函数，用于处理配置值的字符串、字典、数值和枚举类型
    
    Args:
        value: 需要处理的配置值
        
    Returns:
        处理后的配置值
    """
    if isinstance(value, (str, int, float, bool)):
        return value
    elif isinstance(value, dict):
        return value
    elif hasattr(value, 'value'):
        # 处理枚举类型或其他有value属性的对象
        return value.value
    else:
        # 如果不是预期的类型，直接返回原值
        return value 