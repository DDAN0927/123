# -*- coding: utf-8 -*-
import re
import json
from typing import List, Dict, Any, Optional, Callable
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

load_dotenv()

logger = logging.getLogger("ReActAgent")
logger.setLevel(logging.INFO)
file_handler = RotatingFileHandler("agent.log", maxBytes=500*1024*1024, backupCount=5, encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

MAX_HISTORY_ROUNDS = 10


class ReActAgent:
    def __init__(
        self,
        llm,
        tools: List[Callable],
        system_prompt: str = None,
        max_iterations: int = 5,
        enable_reflection: bool = True
    ):
        self.llm = llm
        self.tools = {tool.name: tool for tool in tools}
        self.max_iterations = max_iterations
        self.enable_reflection = enable_reflection
        self.conversation_history = []
        self.last_thinking = []

        self.system_prompt = system_prompt or """你是 SmartPal，一个有独立思考能力的智能助手。

## 你的性格
- 你有自己的想法和观点，不是简单的问答机器
- 你会主动思考用户真正需要什么，而不只是回答表面问题
- 你会在回答后主动给出相关建议或延伸思考
- 你有好奇心，遇到有趣的话题会分享你的见解

## 思考框架
每次收到问题，按以下框架思考：

1. **理解**：用户真正想问什么？有没有隐含需求？
2. **分析**：这个问题需要什么信息？我是否需要工具辅助？
3. **思考**：我对这个问题有什么看法？有没有更深入的视角？
4. **行动**：如果需要工具，调用工具获取信息
5. **反思**：我的回答是否完整？有没有遗漏？用户可能还想知道什么？
6. **回答**：给出有深度的回答，包含你的思考和建议

## 工具使用格式
```
Thought: 你的思考过程（包含理解、分析、你的观点）
Action: 工具名称
Action Input: {"key": "value"}
```

如果不需要工具，直接回答：
```
Thought: 你的思考过程
Reflection: 自我审视——我的回答是否完整？有没有遗漏？用户可能还想知道什么？
Answer: 你的回答（包含你的见解和主动建议）
```

## 回答原则
- 不只回答问题，还要给出你的思考和见解
- 主动建议相关的后续行动或信息
- 如果发现用户可能有未表达的隐含需求，主动提出
- 回答要有深度，但不要啰嗦
"""

    def _trim_history(self):
        max_messages = MAX_HISTORY_ROUNDS * 2
        if len(self.conversation_history) > max_messages:
            self.conversation_history = self.conversation_history[-max_messages:]

    def _strip_outer_code_block(self, text: str) -> str:
        text = text.strip()
        if text.startswith('```') and text.endswith('```'):
            first_newline = text.find('\n')
            if first_newline != -1:
                inner = text[first_newline + 1:]
                if inner.rstrip().endswith('```'):
                    inner = inner.rstrip()[:-3].rstrip()
                if re.search(r'(Thought|Action|Answer|Reflection)\s*:', inner):
                    return inner
            else:
                inner = text[3:-3].strip()
                if re.search(r'(Thought|Action|Answer|Reflection)\s*:', inner):
                    return inner
        return text

    def _parse_llm_output(self, text: str) -> Dict[str, Any]:
        result = {
            "thought": "",
            "reflection": "",
            "action": None,
            "action_input": {},
            "answer": None
        }

        cleaned = self._strip_outer_code_block(text)

        thought_match = re.search(r"Thought\s*:\s*(.+?)(?=\n\s*(Action|Reflection|Observation|Answer|$))", cleaned, re.DOTALL)
        if thought_match:
            result["thought"] = thought_match.group(1).strip()

        action_match = re.search(r"Action\s*:\s*(\w+)", cleaned)
        if action_match:
            result["action"] = action_match.group(1)

            input_match = re.search(r"Action\s*Input\s*:\s*(\{.+?\})(?=\s*(?:Observation|Thought|Action|Reflection|Answer|$))", cleaned, re.DOTALL)
            if input_match:
                raw = input_match.group(1).strip()
                try:
                    result["action_input"] = json.loads(raw)
                except json.JSONDecodeError:
                    parsed_input = raw.strip("{}").strip()
                    result["action_input"] = {"query": parsed_input}

        reflection_match = re.search(r"Reflection\s*:\s*(.+?)(?=\n\s*(Answer|$))", cleaned, re.DOTALL)
        if reflection_match:
            result["reflection"] = reflection_match.group(1).strip()

        if result["action"] is None:
            answer_match = re.search(r"Answer\s*:\s*(.+)", cleaned, re.DOTALL)
            if answer_match:
                result["answer"] = answer_match.group(1).strip()

        return result

    def _build_tool_descriptions(self) -> str:
        lines = []
        for name, tool in self.tools.items():
            lines.append(f"- {name}: {tool.description}")
        return "\n".join(lines)

    def _build_human_message(self, content: str, images: list = None):
        if images:
            content_parts = [{"type": "text", "text": content}]
            for img_url in images:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": img_url}
                })
            return HumanMessage(content=content_parts)
        return HumanMessage(content=content)

    def _reflect_on_answer(self, user_input: str, answer: str, thought: str) -> str:
        if not self.enable_reflection:
            return answer

        try:
            reflect_prompt = f"""你刚才回答了用户的问题，请审视你的回答并改进。

用户问题：{user_input}
你的思考：{thought}
你的回答：{answer}

请从以下角度审视：
1. 回答是否完整？有没有遗漏重要信息？
2. 用户可能还有哪些隐含需求没有被发现？
3. 你有没有更有价值的见解或建议可以补充？

如果回答已经很好，直接返回原回答。
如果需要改进，返回改进后的回答。

直接输出改进后的回答内容，不要加任何前缀："""

            messages = [SystemMessage(content=self.system_prompt)]
            messages.append(HumanMessage(content=reflect_prompt))

            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self.llm.invoke, messages)
                try:
                    response = future.result(timeout=30)
                    improved = response.content.strip()
                    logger.info(f"反思结果: {improved[:200]}")
                    return improved if improved else answer
                except FutureTimeout:
                    logger.warning("反思步骤超时，使用原始回答")
                    return answer
        except Exception as e:
            logger.warning(f"反思步骤失败: {e}")
            return answer

    def invoke(self, input_dict: Dict[str, Any]) -> Dict[str, Any]:
        user_input = input_dict.get("input", "")
        images = input_dict.get("images", [])
        logger.info(f"收到用户输入: {user_input[:100]} (图片: {len(images)}张)")

        self.last_thinking = []
        tool_descriptions = self._build_tool_descriptions()
        scratchpad = ""
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            logger.info(f"开始第 {iteration} 轮推理")

            prompt = f"""可用工具：
{tool_descriptions}

用户问题：{user_input}

{scratchpad}"""

            messages = [SystemMessage(content=self.system_prompt)]
            for msg in self.conversation_history:
                messages.append(msg)
            messages.append(self._build_human_message(prompt, images if iteration == 1 else None))

            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(self.llm.invoke, messages)
                    try:
                        response = future.result(timeout=90)
                    except FutureTimeout:
                        logger.error("LLM 调用超时（90秒）")
                        return {
                            "output": "抱歉，AI 思考时间过长，请稍后重试或简化您的问题。",
                            "thinking": self.last_thinking,
                        }
            except Exception as e:
                error_msg = str(e)
                logger.error(f"LLM 调用失败: {error_msg}")
                if "401" in error_msg:
                    return {
                        "output": "❌ API Key 无效 (401)，请在左侧边栏更新 API Key。",
                        "thinking": self.last_thinking,
                    }
                elif "429" in error_msg:
                    return {
                        "output": "❌ 请求过于频繁 (429)，请稍后重试。",
                        "thinking": self.last_thinking,
                    }
                elif "402" in error_msg:
                    return {
                        "output": "❌ 余额不足 (402)，请充值后重试。",
                        "thinking": self.last_thinking,
                    }
                else:
                    return {
                        "output": f"❌ AI 调用失败: {error_msg[:200]}",
                        "thinking": self.last_thinking,
                    }

            llm_output = response.content
            if isinstance(llm_output, list):
                llm_output = " ".join([c.get("text", "") for c in llm_output if isinstance(c, dict)])
            logger.info(f"LLM 输出: {llm_output}")

            parsed = self._parse_llm_output(llm_output)

            if parsed["thought"]:
                self.last_thinking.append(parsed["thought"])
            if parsed["reflection"]:
                self.last_thinking.append(f"[反思] {parsed['reflection']}")

            if parsed["answer"] is not None:
                final_answer = parsed["answer"]

                if self.enable_reflection and not parsed["reflection"]:
                    final_answer = self._reflect_on_answer(user_input, final_answer, parsed["thought"])

                logger.info(f"得到答案: {final_answer[:200]}")
                self.conversation_history.append(HumanMessage(content=user_input))
                self.conversation_history.append(AIMessage(content=final_answer))
                self._trim_history()
                return {
                    "output": final_answer,
                    "thinking": self.last_thinking,
                }

            if parsed["action"] is not None:
                tool_name = parsed["action"]
                tool_input = parsed["action_input"]

                if tool_name in self.tools:
                    logger.info(f"调用工具: {tool_name} with input: {tool_input}")
                    try:
                        tool = self.tools[tool_name]
                        observation = tool.invoke(tool_input)
                        logger.info(f"工具返回: {observation}")
                        self.last_thinking.append(f"[工具 {tool_name}] {str(observation)[:100]}")
                    except Exception as e:
                        observation = f"工具执行错误: {str(e)}"
                        logger.error(observation)

                    scratchpad += f"""
Thought: {parsed['thought']}
Action: {tool_name}
Action Input: {json.dumps(tool_input, ensure_ascii=False)}
Observation: {observation}
"""
                else:
                    scratchpad += f"""
Thought: {parsed['thought']}
Action: {tool_name}
Observation: 未知工具: {tool_name}，可用工具: {', '.join(self.tools.keys())}
"""
            else:
                logger.info("未解析到 Action，直接返回 LLM 输出")
                self.conversation_history.append(HumanMessage(content=user_input))
                self.conversation_history.append(AIMessage(content=llm_output))
                self._trim_history()
                return {
                    "output": llm_output,
                    "thinking": self.last_thinking,
                }

        final_answer = "抱歉，我无法在规定的迭代次数内解决这个问题。请尝试更简洁地描述您的问题。"
        logger.warning(final_answer)
        self.conversation_history.append(HumanMessage(content=user_input))
        self.conversation_history.append(AIMessage(content=final_answer))
        self._trim_history()
        return {
            "output": final_answer,
            "thinking": self.last_thinking,
        }
