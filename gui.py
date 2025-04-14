import subprocess
import ctypes
import sys
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import webbrowser
import darkdetect
import requests
import logging
import shutil
import json
import platform
from datetime import datetime

# 检查是否以管理员身份运行
def is_admin():
    """检查是否以管理员身份运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

# 配置日志记录
def setup_logging():
    """配置日志记录"""
    logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    log_file = os.path.join(logs_dir, "app.log")
    
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    logging.getLogger('').addHandler(console_handler)
    
    logging.info("日志记录已初始化")

# 执行命令
def execute_commands(commands):
    """执行命令"""
    if not is_admin() and platform.system() == "Windows":
        messagebox.showwarning("权限不足", "请以管理员身份运行此程序以执行此操作。")
        return False
    
    for cmd in commands:
        try:
            result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
            logging.info(f"成功执行: {cmd}")
            if any(keyword in result.stdout.lower() or keyword in result.stderr.lower() 
                   for keyword in ["error", "false", "失败", "错误"]):
                logging.error(f"命令执行失败: {cmd}\n输出: {result.stdout}\n错误: {result.stderr}")
                messagebox.showerror("错误", f"命令执行失败: {cmd}\n错误信息: {result.stderr}")
                return False
        except subprocess.CalledProcessError as e:
            logging.error(f"命令执行失败: {cmd}\n错误信息: {e.stderr}")
            messagebox.showerror("错误", f"命令执行失败: {cmd}\n错误信息: {e.stderr}")
            return False
    
    return True

# 获取 GitHub520 的 JSON 格式的 hosts 内容
def get_github520_json():
    """从GitHub520获取JSON格式的hosts内容"""
    try:
        response = requests.get("https://raw.hellogithub.com/hosts.json")
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"获取GitHub520 JSON失败，状态码: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"获取GitHub520 JSON失败: {e}")
        return None
    
# 从 JSON 中提取 hosts 内容
def json_to_hosts_format(json_data):
    """将JSON数据转换为hosts文件格式"""
    try:
        if not isinstance(json_data, list):
            logging.error("无效的JSON数据格式: 输入不是列表")
            return None
            
        hosts_lines = []
        valid_entries = 0
        logging.info(f"开始处理 {len(json_data)} 条记录")
        
        for entry in json_data:
            try:
                # 验证每个条目格式
                if not isinstance(entry, list) or len(entry) < 2:
                    logging.warning(f"跳过无效条目: {entry} - 格式不正确")
                    continue
                
                ip = str(entry[0]).strip()
                domain = entry[1]
                
                # 验证IP地址格式
                if not all(part.isdigit() and 0 <= int(part) <= 255 for part in ip.split('.')):
                    logging.warning(f"跳过无效IP: {ip}")
                    continue
                
                # 处理单个域名或域名列表
                domains = []
                if isinstance(domain, list):
                    domains = [str(d).strip() for d in domain]
                else:
                    domains = [str(domain).strip()]
                
                # 过滤空域名
                domains = [d for d in domains if d]
                if not domains:
                    logging.warning(f"跳过无效域名条目: {entry}")
                    continue
                
                # 构建hosts条目
                hosts_lines.append(f"{ip} {' '.join(domains)}")
                valid_entries += 1
                
            except Exception as e:
                logging.warning(f"处理条目时出错: {entry} - {str(e)}")
                continue
        
        # 生成最终hosts内容
        if not hosts_lines:
            logging.error("没有有效的hosts条目")
            return None
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        header = f"\n\n# GitHub520 Start - 更新时间: {now}\n"
        footer = "\n# GitHub520 End\n"
        
        result = header + "\n".join(hosts_lines) + footer
        logging.info(f"成功解析 {valid_entries}/{len(json_data)} 条记录")
        logging.debug(f"生成的hosts内容预览:\n{result[:200]}...")  # 只记录前200字符
        
        return result
        
    except Exception as e:
        logging.error(f"JSON转换失败: {str(e)}", exc_info=True)
        return None

def update_hosts_file(hosts_content):
    """更新hosts文件（仅Windows）"""
    try:
        # 使用正确的系统hosts路径
        hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
        
        # 确保hosts_content是字符串
        if not isinstance(hosts_content, str):
            logging.error("无效的hosts内容类型")
            return False
            
        # 检查内容是否有效
        if not hosts_content.strip():
            logging.error("空的hosts内容")
            return False
            
        # 请求管理员权限
        if not is_admin():
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, 
                f'"{sys.argv[0]}" --update-hosts', 
                None, 1
            )
            return False
            
        # 读取现有内容
        with open(hosts_path, "r", encoding="utf-8") as f:
            existing_content = f.read()
        
        # 处理现有内容
        start_marker = "# GitHub520 Start"
        end_marker = "# GitHub520 End"
        
        if start_marker in existing_content and end_marker in existing_content:
            parts = existing_content.split(start_marker)
            existing_content = parts[0] + parts[-1].split(end_marker)[-1]
        
        # 写入新内容
        with open(hosts_path, "w", encoding="utf-8") as f:
            f.write(existing_content.strip())
            f.write("\n\n")
            f.write(hosts_content)
        
        # 刷新DNS
        subprocess.run("ipconfig /flushdns", shell=True, check=True)
        return True
        
    except Exception as e:
        logging.error(f"更新hosts文件失败: {str(e)}", exc_info=True)
        return False

def update_github520_hosts():
    """主更新函数"""
    try:
        json_data = get_github520_json()
        if not json_data:
            logging.error("获取JSON数据失败")
            messagebox.showerror("错误", "获取GitHub520数据失败")
            return False
            
        hosts_content = json_to_hosts_format(json_data)
        if not hosts_content:
            logging.error("生成hosts内容失败")
            messagebox.showerror("错误", "转换hosts内容失败")
            return False
            
        if not update_hosts_file(hosts_content):
            logging.error("更新hosts文件失败")
            messagebox.showerror("错误", "更新hosts文件失败")
            return False
            
        logging.info("GitHub520 hosts更新成功")
        messagebox.showinfo("成功", "GitHub520 hosts更新成功")
        return True
        
    except Exception as e:
        logging.error(f"更新过程失败: {str(e)}", exc_info=True)
        messagebox.showerror("错误", f"更新失败: {str(e)}")
        return False
    
# 移除 GitHub520 的 hosts 内容
def remove_github520_hosts():
    """移除 GitHub520 的 hosts 内容"""
    try:
        hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
        
        # 请求管理员权限
        if not is_admin():
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, 
                f'"{sys.argv[0]}" --remove-hosts', 
                None, 1
            )
            return False
        
        # 读取 hosts 文件内容
        with open(hosts_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # 过滤掉 GitHub520 的内容
        new_lines = []
        in_github520_section = False
        for line in lines:
            if "# GitHub520 Start" in line:
                in_github520_section = True
                continue
            if "# GitHub520 End" in line:
                in_github520_section = False
                continue
            if not in_github520_section:
                new_lines.append(line)
        
        # 写入新的 hosts 文件
        with open(hosts_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        
        # 刷新 DNS 缓存
        subprocess.run("ipconfig /flushdns", shell=True, check=True)
        
        logging.info("成功移除GitHub520 hosts")
        messagebox.showinfo("成功", "已成功移除GitHub520 hosts")
        return True
        
    except Exception as e:
        logging.error(f"移除 GitHub520 hosts 失败: {str(e)}", exc_info=True)
        messagebox.showerror("错误", f"移除失败: {str(e)}")
        return False


# 打开 GitHub 链接
def open_github():
    """打开 GitHub 链接"""
    webbrowser.open("https://github.com/WavesMan/GitHub520-Python")

# 将窗口居中显示
def center_window(window, width, height):
    """将窗口居中显示"""
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")

# 显示工具界面
def show_tools_frame():
    """显示工具界面"""
    about_frame.pack_forget()
    tools_frame.pack(fill=tk.BOTH, expand=True)

# 显示关于界面
def show_about_frame():
    """显示关于界面"""
    tools_frame.pack_forget()
    about_frame.pack(fill=tk.BOTH, expand=True)

# 从 GitHub 仓库获取最新版本信息
def get_latest_version():
    """从 GitHub 仓库获取最新版本信息"""
    try:
        response = requests.get("https://api.github.com/repos/WavesMan/GitHub520-Python/releases/latest")
        if response.status_code == 200:
            latest_version = response.json()["tag_name"]
            latest_version_label.config(text=f"最新版本: {latest_version}")
        else:
            latest_version_label.config(text="无法获取版本信息")
    except Exception as e:
        latest_version_label.config(text=f"获取最新版本失败: {e}")

# 鼠标悬停时高亮背景
def on_enter(event, widget=None):
    """鼠标悬停时高亮背景"""
    target = widget if widget else event.widget
    target.config(background="#f0f0f0")
    sync_background_color(target, "#f0f0f0")

# 鼠标离开时恢复背景
def on_leave(event, widget=None):
    """鼠标离开时恢复背景"""
    target = widget if widget else event.widget
    target.config(background="white")
    sync_background_color(target, "white")

# 确保子控件的背景颜色与父容器同步
def sync_background_color(frame, color):
    """同步父容器和子控件的背景颜色"""
    for child in frame.winfo_children():
        child.config(bg=color)

# 导出日志文件
def export_logs():
    """导出日志文件"""
    logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    log_file = os.path.join(logs_dir, "app.log")
    
    if not os.path.exists(log_file):
        messagebox.showwarning("警告", "未找到日志文件！")
        logging.warning("未找到日志文件")
        return
    
    save_path = filedialog.asksaveasfilename(
        defaultextension=".log",
        filetypes=[("日志文件", "*.log")],
        title="保存日志文件"
    )
    
    if save_path:
        try:
            shutil.copy(log_file, save_path)
            messagebox.showinfo("成功", f"日志文件已导出到：{save_path}")
            logging.info(f"日志文件已导出到：{save_path}")
        except Exception as e:
            messagebox.showerror("错误", f"导出日志文件失败：{e}")
            logging.error(f"导出日志文件失败：{e}")



###################
###################
####    GUI    ####
###################
###################



# 创建 GUI 界面
def create_gui():
    """创建 GUI 界面"""
    setup_logging()
    global tools_frame, about_frame, latest_version_label

    # 创建主窗口
    root = tk.Tk()
    root.title("GitHub DNS HOSTS 修改器")

    # 设置窗口大小
    window_width = 550
    window_height = 450
    root.geometry(f"{window_width}x{window_height}")

    # 将窗口居中显示
    center_window(root, window_width, window_height)

    # 设置窗口图标
    try:
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        icon_path = os.path.join(base_path, "github.ico")
        root.iconbitmap(icon_path)
    except tk.TclError as e:
        logging.error(f"无法加载图标文件: {e}")

    # 设置主题
    style = ttk.Style()
    style.theme_use("vista")

    # 动态检测系统主题并设置颜色
    if darkdetect.isDark():
        sidebar_color = "#2d2d2d"
        button_color = sidebar_color
        text_color = "#ffffff"
    else:
        sidebar_color = "#e1f5fe"
        button_color = sidebar_color
        text_color = "#000000"

    # 创建侧边栏
    sidebar = tk.Frame(root, bg=sidebar_color, width=120)
    sidebar.pack(side=tk.LEFT, fill=tk.Y)

    # 添加侧边栏按钮
    tools_button = tk.Button(
        sidebar,
        text="工具",
        font=("Microsoft YaHei", 12),
        bg=button_color,
        fg=text_color,
        activebackground=button_color,
        activeforeground="#005bb5",
        bd=0,
        relief=tk.FLAT,
        cursor="hand2",
        command=show_tools_frame,
    )
    tools_button.pack(pady=10, padx=10, fill=tk.X)

    about_button = tk.Button(
        sidebar,
        text="关于",
        font=("Microsoft YaHei", 12),
        bg=button_color,
        fg=text_color,
        activebackground=button_color,
        activeforeground="#005bb5",
        bd=0,
        relief=tk.FLAT,
        cursor="hand2",
        command=show_about_frame,
    )
    about_button.pack(pady=10, padx=10, fill=tk.X)

    # 创建工具界面
    tools_frame = ttk.Frame(root)

    # GitHub520 管理
    github520_label = ttk.Label(tools_frame, text="GitHub DNS HOSTS 修改器", font=("Microsoft YaHei", 14))
    github520_label.pack(pady=10)

    github520_button_frame = ttk.Frame(tools_frame)
    github520_button_frame.pack()

    def update_github520():
        """更新 GitHub520 hosts"""
        json_data = get_github520_json()
        if json_data:
            # 先转换为hosts格式
            hosts_content = json_to_hosts_format(json_data)
            if hosts_content:
                if update_hosts_file(hosts_content):
                    messagebox.showinfo("成功", "已成功更新 GitHub520 hosts")
                else:
                    messagebox.showerror("错误", "更新 GitHub520 hosts 失败")
            else:
                messagebox.showerror("错误", "转换 GitHub520 hosts 内容失败")
        else:
            messagebox.showerror("错误", "获取 GitHub520 hosts 内容失败")

    update_github520_button = ttk.Button(
        github520_button_frame,
        text="更新 GitHub HOST",
        style="TButton",
        command=update_github520,
    )
    update_github520_button.pack(side=tk.LEFT, padx=10, pady=10)

    remove_github520_button = ttk.Button(
        github520_button_frame,
        text="移除 GitHuB HOST",
        style="TButton",
        command=lambda: remove_github520_hosts() and messagebox.showinfo("成功", "已成功移除 GitHub520 hosts"),
    )
    remove_github520_button.pack(side=tk.LEFT, padx=10, pady=10)

    # 创建关于界面
    about_frame = ttk.Frame(root)
    about_label = ttk.Label(
        about_frame,
        text="关于本应用程序",
        font=("Microsoft YaHei", 14),
        anchor="w",
    )
    about_label.pack(pady=20, padx=20, fill=tk.X)

    # 当前程序版本
    version_label = tk.Label(
        about_frame,
        text="当前程序版本: v1.0",
        font=("Microsoft YaHei", 12),
        bg="white",
        anchor="w",
        height=2,
    )
    version_label.pack(pady=5, padx=20, fill=tk.X, ipady=5)
    version_label.bind("<Enter>", lambda event: on_enter(event, version_label))
    version_label.bind("<Leave>", lambda event: on_leave(event, version_label))

    # 开发者信息
    developer_label = tk.Label(
        about_frame,
        text="开发者: WavesMan",
        font=("Microsoft YaHei", 12),
        bg="white",
        anchor="w",
        height=2,
    )
    developer_label.pack(pady=5, padx=20, fill=tk.X, ipady=5)
    developer_label.bind("<Enter>", lambda event: on_enter(event, developer_label))
    developer_label.bind("<Leave>", lambda event: on_leave(event, developer_label))

    # 仓库地址
    repo_frame = tk.Frame(about_frame, bg="white")
    repo_frame.pack(pady=5, padx=20, fill=tk.X, ipady=5)

    repo_text_label = tk.Label(
        repo_frame,
        text="仓库地址:",
        font=("Microsoft YaHei", 10),
        fg="black",
        bg="white",
        anchor="w",
    )
    repo_text_label.pack(fill=tk.X)

    repo_link_label = tk.Label(
        repo_frame,
        text="https://github.com/WavesMan/GitHub520-Python",
        font=("Microsoft YaHei", 10),
        bg="white",
        cursor="hand2",
        anchor="w",
    )
    repo_link_label.pack(fill=tk.X)

    repo_link_label.bind("<Button-1>", lambda event: open_github())
    repo_frame.bind("<Enter>", lambda event: on_enter(event, repo_frame))
    repo_frame.bind("<Leave>", lambda event: on_leave(event, repo_frame))

    # 获取最新版本
    latest_version_label = tk.Label(
        about_frame,
        text="点击此处获取最新版本",
        font=("Microsoft YaHei", 12),
        bg="white",
        cursor="hand2",
        anchor="w",
        height=2,
    )
    latest_version_label.pack(pady=5, padx=20, fill=tk.X, ipady=5)
    latest_version_label.bind("<Enter>", lambda event: on_enter(event, latest_version_label))
    latest_version_label.bind("<Leave>", lambda event: on_leave(event, latest_version_label))
    latest_version_label.bind("<Button-1>", lambda event: get_latest_version())

    # 导出日志
    export_logs_label = tk.Label(
        about_frame,
        text="导出运行日志",
        font=("Microsoft YaHei", 12),
        bg="white",
        cursor="hand2",
        anchor="w",
        height=2,
    )
    export_logs_label.pack(pady=5, padx=20, fill=tk.X, ipady=5)
    export_logs_label.bind("<Enter>", lambda event: on_enter(event, export_logs_label))
    export_logs_label.bind("<Leave>", lambda event: on_leave(event, export_logs_label))
    export_logs_label.bind("<Button-1>", lambda event: export_logs())

    # 默认显示工具界面
    show_tools_frame()

    # 添加页脚文字
    footer_label = ttk.Label(
        root,
        text="Powered by GitHub@WavesMan",
        font=("Microsoft YaHei", 10),
        foreground="gray",
        cursor="hand2",
    )
    footer_label.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)

    footer_label.bind("<Button-1>", lambda event: open_github())

    # 运行主循环
    root.mainloop()

if __name__ == "__main__":
    setup_logging()
    create_gui()
