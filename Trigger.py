import time
from chipshouter import ChipSHOUTER

# 初始化连接
cs = ChipSHOUTER("COM7")

def setup_hardware_trigger():
    print("正在配置硬件触发模式...")
    
    # 基础脉冲参数
    cs.voltage = 300
    cs.pulse.width = 160
    
    # --- 修正后的触发配置 ---
    # 使用 .trigger.source 替代 .trig_src
    # "ext" 代表外部 SMB 接口，"sw" 代表软件串口
    cs.trigger.source = "ext" 
    
    # 使用 .trigger.edges 替代 .trig_edge
    # "rising" 代表上升沿，"falling" 代表下降沿
    cs.trigger.edges = "rising" 
    
    # 激活高压 (Arming)
    cs.armed = 1
    
    time.sleep(1.5)
    print(f"设备已就绪！状态: {cs.state}")
    print("等待开发板 PTA19 (J2-5) 的物理信号...")

setup_hardware_trigger()

try:
    while True:
        # 必须定期检查以防止 Sensor Fault 报警
        cs.trigger_safe 
        time.sleep(0.5)
except KeyboardInterrupt:
    cs.armed = 0