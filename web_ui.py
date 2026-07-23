# import streamlit as st
# from chat_engine import PhantasmChat

# # --- 1. 初始化 ---
# st.set_page_config(page_title="Phantasm Terminal", layout="wide")

# if "chat_instance" not in st.session_state:
#     st.session_state.chat_instance = PhantasmChat()

# # --- 2. 侧边栏（保持你的需求：查看完整历史元数据） ---
# with st.sidebar:
#     st.title("核心状态")
#     st.write(f"当前记忆长度: {len(st.session_state.chat_instance.history)}")
#     if st.button("清空本地缓存"):
#         st.session_state.chat_instance.history = [st.session_state.chat_instance.system_message]
#         st.rerun()

# # --- 3. 聊天容器 ---
# # 我们不再只显示最后一句话，而是遍历历史记录
# # 注意：排除掉 index 0 的 system_prompt，因为它不需要显示给用户
# for msg in st.session_state.chat_instance.history[1:]:
#     # Streamlit 的 chat_message 会根据 label 自动处理左右布局
#     # "user" 靠右，"assistant" 靠左
#     role = "user" if msg["role"] == "user" else "assistant"
#     avatar = "👤" if role == "user" else "🔮" # 你以后可以换成影子的头像路径
    
#     with st.chat_message(role, avatar=avatar):
#         st.markdown(msg["content"])

# # --- 4. 底部输入与响应逻辑 ---
# if prompt := st.chat_input("输入你的指令..."):
#     # 立即在前端渲染用户输入（增强即时感）
#     with st.chat_message("user", avatar="👤"):
#         st.markdown(prompt)
    
#     # 调用后端逻辑
#     with st.chat_message("assistant", avatar="🔮"):
#         # 先占位，显示加载状态
#         response_placeholder = st.empty()
        
#         # 获取回复
#         reply = st.session_state.chat_instance.get_response(prompt)
        
#         # 渲染正式回复
#         response_placeholder.markdown(reply)
    
#     # 保持页面状态同步
#     st.rerun()