from langdetect import detect
from Reaearch_Idea.code import bk_prompt as pmt
from openai import OpenAI,APIConnectionError
import os
import re, ast
import logging

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", ""),
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    timeout=600,         
    max_retries=0 
)


    
import time
from openai import APIConnectionError, OpenAIError
from httpx import RemoteProtocolError

def query_Gemini(messages, model, stream=True, max_retries=6, backoff=1.0):
    attempt = 0
    while True:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                stream=stream,
                timeout=900,
                temperature=0,
                # 可选：若你不需要工具调用，硬关掉它以避免“空文本”
                # tool_choice="none"
            )
            # 不要打印 resp（有些对象 __repr__ 可能触发访问）；只打类型
            print(f"API 返回（type）：{type(resp)}")
            break
        except (APIConnectionError, RemoteProtocolError) as e:
            if attempt < max_retries:
                wait = backoff * (2 ** attempt)
                print(f"[警告] 第 {attempt + 1} 次请求失败：{e}，{wait:.1f}s 后重试...")
                time.sleep(wait); attempt += 1; continue
            raise RuntimeError("多次重试后仍无法连接 OpenAI") from e
        except OpenAIError:
            raise

    text_buf = []
    tool_arg_buf = []
    finish_reason = None

    try:
        for chunk in resp:
            # 某些心跳块可能没有 choices
            if not getattr(chunk, "choices", None):
                continue
            choice = chunk.choices[0]
            if getattr(choice, "finish_reason", None):
                finish_reason = choice.finish_reason

            delta = getattr(choice, "delta", None)
            if not delta:
                continue

            # 1) 正常文本
            content = getattr(delta, "content", None)
            if content:
                # 旧 Chat Completions：content 是 str；新式多模：可能是 list
                if isinstance(content, str):
                    print(content, end="", flush=True)
                    text_buf.append(content)
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            t = part.get("text") or ""
                            print(t, end="", flush=True)
                            text_buf.append(t)

            # 2) 旧式 function_call
            fc = getattr(delta, "function_call", None)
            if fc and getattr(fc, "arguments", None):
                tool_arg_buf.append(fc.arguments)

            # 3) 新式 tool_calls（数组）
            tcs = getattr(delta, "tool_calls", None)
            if tcs:
                for tc in tcs:
                    fn = getattr(tc, "function", None)
                    if fn and getattr(fn, "arguments", None):
                        tool_arg_buf.append(fn.arguments)

        print()  # 换行
    except (RemoteProtocolError, APIConnectionError) as e:
        # 流中断 → 降级一次非流式
        if attempt < max_retries:
            wait = backoff * (2 ** attempt)
            print(f"\n[警告] 流式读取中断：{e}，{wait:.1f}s 后降级到非流式...")
            time.sleep(wait); attempt += 1
            resp_non = client.chat.completions.create(
                model=model, messages=messages, stream=False, timeout=900
            )
            content = (resp_non.choices[0].message.content
                       or (getattr(resp_non.choices[0].message, "function_call", None) and
                           resp_non.choices[0].message.function_call.arguments)
                       or "")
            print(content)
            return content.strip()
        raise RuntimeError("在流式读取过程中多次失败，已放弃") from e

    # —— 收尾：优先返回文本；无文本则尝试工具参数；仍无→非流式兜底 ——
    out = "".join(text_buf).strip()

    if not out and tool_arg_buf:
        # 你也可以选择直接 raise，取决于你的期望输出
        out = "\n".join(tool_arg_buf).strip()

    if not out:
        # 再做一次非流式兜底（有时模型只给了工具调用）
        resp_non = client.chat.completions.create(
            model=model, messages=messages, stream=False, timeout=900
        )
        out = (resp_non.choices[0].message.content
               or (getattr(resp_non.choices[0].message, "function_call", None) and
                   resp_non.choices[0].message.function_call.arguments)
               or "")

    # 打点：帮助定位空输出的“根因”
    print(f"[DEBUG] finish_reason={finish_reason}, "
          f"text_len={len(out)}, tool_args_captured={len(tool_arg_buf)}>0? {bool(tool_arg_buf)}")

    return out




def gpt_query(messages, model):
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0
    )
    logging.debug(f"API 返回（type）：{type(response)}")
    return response.choices[0].message.content.strip()


def llm_translate(text):
    messages = pmt.template("translate", text=text)
    return gpt_query(messages, model="gpt-4o")

def llm_rewrite(query):
    messages = pmt.template("rewrite", query=query)
    return gpt_query(messages,model="gpt-4o")

def is_english(text: str) -> bool:
    try:
        return detect(text) == "en"
    except:
        return False


def preprocess_user_query(query: str) -> str:
    #判断是否是英文
    if not is_english(query):
        translate_query = llm_translate(query)
    else:
        translate_query = query
    #问题重写
    rewriteen_query = llm_rewrite(translate_query)
    return rewriteen_query

def get_keywords(query: str) -> list:
    # 关键词提取
    messages = pmt.template("keyword", query=query)
    raw = gpt_query(messages, model="gpt-4o")
    return ast.literal_eval(raw.strip())
