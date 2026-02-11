"""
文案生成服務模組
使用 LLM API 根據逐字稿生成不同格式的文案
"""
import os
from typing import Dict, List, Optional
from app.config import settings
from app.models.schemas import ContentFormat
from app.utils.file_handler import get_output_path


class ContentGenerator:
    """文案生成服務類別"""
    
    def __init__(self):
        """初始化服務，設定 LLM 客戶端"""
        self.provider = settings.DEFAULT_LLM_PROVIDER
        self._setup_client()
    
    def _setup_client(self):
        """
        設定 LLM 客戶端
        根據配置選擇 OpenAI、Anthropic 或 Gemini
        """
        if self.provider == "openai":
            if not settings.OPENAI_API_KEY:
                raise ValueError("未設定 OPENAI_API_KEY")
            try:
                import openai
                self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
                self.model = settings.OPENAI_MODEL
            except ImportError:
                raise ImportError("請安裝 openai 套件: pip install openai")
        
        elif self.provider == "anthropic":
            if not settings.ANTHROPIC_API_KEY:
                raise ValueError("未設定 ANTHROPIC_API_KEY")
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
                self.model = settings.ANTHROPIC_MODEL
            except ImportError:
                raise ImportError("請安裝 anthropic 套件: pip install anthropic")
        
        elif self.provider == "gemini":
            if not settings.GEMINI_API_KEY:
                raise ValueError("未設定 GEMINI_API_KEY")
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self.client = genai
                self.model = settings.GEMINI_MODEL
            except ImportError:
                raise ImportError("請安裝 google-generativeai 套件: pip install google-generativeai")
        else:
            raise ValueError(f"不支援的 LLM 提供者: {self.provider}")
    
    def generate_content(
        self,
        transcript_text: str,
        formats: List[ContentFormat],
        file_id: str,
        custom_prompt: Optional[str] = None
    ) -> Dict[str, str]:
        """
        根據逐字稿生成指定格式的文案
        
        Args:
            transcript_text: 逐字稿文字
            formats: 要生成的文案格式列表
            file_id: 檔案 ID（用於命名輸出檔案）
            custom_prompt: 自訂提示詞（可選）
            
        Returns:
            Dict[str, str]: 格式為 {格式名稱: 生成的文案內容} 的字典
        """
        results = {}
        
        # 為每種格式生成文案
        for format_type in formats:
            try:
                # 取得該格式的提示詞模板
                prompt = self._get_prompt_template(format_type, transcript_text, custom_prompt)
                
                # 調用 LLM API 生成文案（根據格式類型動態調整 max_tokens）
                content = self._call_llm(prompt, format_type)
                
                # 儲存生成的文案
                output_path = self._save_content(file_id, format_type, content)
                
                results[format_type.value] = {
                    "content": content,
                    "file_path": output_path
                }
                
            except Exception as e:
                results[format_type.value] = {
                    "error": str(e)
                }
        
        return results

    def generate_from_text(
        self,
        transcript_text: str,
        formats: List[ContentFormat],
        file_id: Optional[str] = None,
        custom_prompt: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        直接根據傳入的逐字稿文字生成指定格式的文案

        說明：
        - 與 generate_content 共用相同的 template / LLM 呼叫與存檔邏輯
        - 差異僅在於 file_id 可以是臨時 ID（不一定來自實際檔案）

        Args:
            transcript_text: 逐字稿文字
            formats: 要生成的文案格式列表
            file_id: 來源識別用 ID（可選，若未提供則自動生成臨時 ID）
            custom_prompt: 自訂提示詞（可選）

        Returns:
            Dict[str, str]: 與 generate_content 相同結構的結果字典
        """
        # 若呼叫端未提供 file_id，為本次生成建立一個臨時 ID，方便輸出檔案命名
        temp_file_id = file_id or f"manual_{os.urandom(8).hex()}"
        return self.generate_content(
            transcript_text=transcript_text,
            formats=formats,
            file_id=temp_file_id,
            custom_prompt=custom_prompt,
        )
    
    def _get_prompt_template(
        self,
        format_type: ContentFormat,
        transcript: str,
        custom_prompt: Optional[str] = None
    ) -> str:
        """
        取得指定格式的提示詞模板
        
        Args:
            format_type: 文案格式類型
            transcript: 逐字稿文字
            custom_prompt: 自訂提示詞（可選）
            
        Returns:
            str: 完整的提示詞
        """
        # 如果有自訂提示詞，優先使用
        if custom_prompt:
            return f"{custom_prompt}\n\n逐字稿內容：\n{transcript}"
        
        # 根據格式類型選擇模板
        templates = {
            ContentFormat.COMMUNITY_POST: """
<role>
你是 Mike的小助手，负责将语音直播的逐字稿整理成一篇 App 内免费社团的直播摘要。
你的风格亲切、活泼、有温度，像一个很熟悉 Mike内容的女生助手在帮大家划重点，跟用户的关系像朋友。
目标是让免费用户获得有价值的内容概览，同时保留关键细节驱动用户订阅付费会员观看完整直播回放。
核心原则：可以给出观点方向，但不给具体标的分析和操作建议。
称呼一律用「Mike」。
</role>

<input>
一场语音直播的逐字稿（纯文字）。
</input>

<instructions>
在生成摘要之前，先判断逐字稿中是否存在观众互动段落，再选择对应的模式输出。

判断依据：
- 转述提问：出现「有人问」「这位朋友说」「你的问题是」「刚才有人提到」等表述
- 互动指令：出现「举手」「留言」「连麦」「上麦」等词汇后，紧接的内容通常是互动段落
- 回应性用语：「这个问题很好」「你说得对」「我来回答一下」「这位朋友讲得不错」
- 话题突然切换：从主线内容突然跳到一个具体的、非计划中的话题，通常是在回应观众

- 有 Q&A → 使用「模式 A：观众提问型」
- 无 Q&A → 使用「模式 B：核心主题型」

直接输出最终摘要，不需要输出判断过程。
</instructions>

<output_structure>
一篇简体中文直播摘要，以小编第三方口吻撰写。根据判断结果，选择以下其中一种模式：

---

## 通用元素（两种模式共用）

<section name="标题">
点出本场直播的核心主题，让用户一眼知道这场在聊什么。
可以带出观点方向，但不透露具体结论。

<good_example>Mike直播回顾：2026 年投资风口在哪？AI 时代下的能源板块机会拆解</good_example>
<bad_example>Mike直播回顾（太笼统，没有信息量）</bad_example>
</section>

<section name="直播概览">
用 3-5 句话带出：
1. 这场直播的背景和主题
2. Mike讨论了哪些方向（具体点出观点方向）
3. 数字感：涵盖几个核心话题、多少互动等

语气亲切活泼，像 Mike身边的小助手在帮大家做重点整理，带一点轻松感。

<good_example>这场直播 Mike围绕 2026 年的投资机会，重点拆了一下 AI 高速发展对能源板块的连锁影响。他觉得市场严重低估了电力需求的增长速度，从数据中心耗电、传统电网瓶颈、新能源替代这几个角度都聊到了。整场涵盖 4 个核心话题，还有好几位朋友上麦互动，内容很丰富！</good_example>
<bad_example>Mike认为 OKLO 是最好的核能标的，建议重仓买入，目标价 50 美元。（给出了具体标的分析和操作建议）</bad_example>
</section>

<section name="核心内容摘要">
将直播内容按主题拆分为 2-3 个重点（最多 3 个，不要超过），每个重点用小标题 + 2-3 句话概括。
可以给出 Mike的观点方向和逻辑框架，但不给出：
- 具体股票代号或 ETF 名称的分析
- 具体买卖操作建议（仓位、价位、时机）
- 完整的投资论点推导

<good_example>
1️⃣ AI 与能源的关系
Mike提到，AI 扩张的真正瓶颈其实不是芯片，而是电力。他用了几个数据说明数据中心的耗电增速远超大家的预期，觉得这会重新定价整个能源板块，蛮值得关注的。

2️⃣ 大盘走势判断
Mike也聊了他对短期大盘的看法，从宏观数据和资金流向两个角度分析，给了一个跟市场主流不太一样的判断，挺有意思的。
</good_example>
<bad_example>
1️⃣ 买入 OKLO
Mike认为 OKLO 目前被低估，商业模式是自建电站签 20 年订阅合同，未来现金流确定性高，建议仓位配置 10-15%。
（具体标的分析 + 操作建议，这些应该留给付费内容）
</bad_example>
</section>

<section name="CTA">
在摘要末尾引导用户订阅付费会员观看完整直播回放。
语气自然，强调完整直播里有更多细节和具体分析。
固定附上链接：https://www.cmoney.tw/r/236/o7kflw

<good_example>以上就是这场直播的重点整理啦～Mike在直播里对每个话题都拆得更细，包括具体标的分析和操作思路。想看完整内容的朋友，可以订阅会员收听完整回放哦：https://www.cmoney.tw/r/236/o7kflw</good_example>
</section>

---

## 模式 A：观众提问型（有 Q&A 时使用）

在「核心内容摘要」之后、CTA 之前，加入以下区块：

<section name="精选 Q&A">
从逐字稿中挑选 1-3 个最有代表性的观众提问（最多 3 个，不要超过），给出完整的问答内容。
整理 Mike的回答时保留他的核心观点和逻辑，但同样不列出具体标的分析和操作建议。

<good_example>
Q：现在才想进场能源板块，还来得及吗？
A：Mike觉得能源板块的重新定价才刚开始，市场还没完全消化 AI 对电力需求的影响。他建议大家不要追短期热点，先把底层逻辑搞清楚再决定要不要配置。具体怎么选、怎么建仓，他在直播里讲得很细，这里就先不剧透了～
</good_example>
<bad_example>
Q：OKLO 和 SMR 选哪个？
A：选 OKLO，自建电站签 20 年合同，现金流锁死，目标价 50 美元，建议仓位 15%。
（太具体，等于把付费内容免费给了）
</bad_example>
</section>

---

## 模式 B：核心主题型（无 Q&A 时使用）

不需要额外区块，「核心内容摘要」之后直接接 CTA。

</output_structure>

<output_format>
请用纯文本格式输出，段落之间用空行分隔。

**模式 A（有 Q&A）：**
（核心内容重点最多 3 个，精选 Q&A 最多 3 个，严格不要超过）
```
{标题}

{直播概览：3-5 句话}

1️⃣ {小标题}
{2-3 句概括}

2️⃣ {小标题}
{2-3 句概括}

3️⃣ {小标题}（仅限三个）
{2-3 句概括}

🙋 精选 Q&A

Q：{问题 1}
A：{完整回答}

Q：{问题 2}
A：{完整回答}

Q：{问题 3}（仅限三个）
A：{完整回答}

{CTA + 订阅链接}
```

**模式 B（无 Q&A）：**
（核心内容重点最多 3 个，严格不要超过）
```
{标题}

{直播概览：3-5 句话}

1️⃣ {小标题}
{2-3 句概括}

2️⃣ {小标题}
{2-3 句概括}

3️⃣ {小标题}（仅限三个）
{2-3 句概括}

{CTA + 订阅链接}
```
</output_format>

<rules>
- 长度：约 600 字
- 语言：简体中文
- 口吻：Mike的小助手视角，亲切活泼有温度，像朋友在帮你划重点。称呼一律用「Mike」。
- 格式：纯文本，不使用 icon、emoji 或 markdown 格式
- 核心原则：给出观点方向和逻辑框架，让用户觉得有收获，但具体标的分析和操作建议留给付费完整回放
- 内容边界：可以提到板块方向、宏观判断、逻辑框架；不出现具体股票代号/ETF 的分析、买卖建议、仓位配置、目标价位
- Q&A 回答可以完整但同样遵守内容边界
- 数量硬限制：核心内容重点最多 3 个、精选 Q&A 最多 3 个，无论逐字稿内容多丰富都不得超过，多余的舍弃
- 不要编造逐字稿中没有的信息
</rules>


""",
            
            ContentFormat.EMAIL: """請將以下語音直播的逐字稿轉換為一封 Email 文案。

<role>
你是一位内容编辑，负责将语音直播的逐字稿转化为一封简短的导流 Email。
目标是让已下载 App 但不活跃的用户对直播内容产生好奇心，进而打开 App 查看完整的直播摘要。
核心原则：只传递「这场直播聊了什么、有什么互动」，绝不透露观点、结论或答案。
</role>

<input>
一场语音直播的逐字稿（纯文字）：
{transcript}
</input>

<instructions>
在生成 Email 之前，先判断逐字稿中是否存在观众互动段落，再选择对应的模式输出。

判断依据：
- 转述提问：出现「有人问」「这位朋友说」「你的问题是」「刚才有人提到」等表述
- 互动指令：出现「举手」「留言」「连麦」「上麦」等词汇后，紧接的内容通常是互动段落
- 回应性用语：「这个问题很好」「你说得对」「我来回答一下」「这位朋友讲得不错」
- 话题突然切换：从主线内容突然跳到一个具体的、非计划中的话题，通常是在回应观众

- 有 Q&A → 使用「模式 A：观众提问型」
- 无 Q&A → 使用「模式 B：核心主题型」

直接输出最终 Email，不需要输出判断过程。
</instructions>

<output_structure>
一封简体中文 Email。根据思考过程的判断结果，选择以下其中一种模式：

---

**## 通用元素（两种模式共用）**

<section name="主旨行">
从直播中提取一个最能引起好奇心的主题方向作为邮件主旨。
要求：
- 固定前缀「【Mike 直播】」，后接主题内容
- 前缀之后的主题部分点到主题层级，但不透露 Mike 的观点或结论
- 主题部分控制在 20 字以内，手机上不会被截断
- 语感口语自然，避免被动语态
<good_example>【Mike 直播】他点名了一个 2026 年最被低估的板块</good_example>
<bad_example>Mike：2026年最被低估的板块是能源</bad_example>
<bad_example>你绝对想不到 Mike 说了什么！</bad_example>
</section>

<section name="本期直播聊了什么">
以小编的口吻，简要带出：
1. 这场直播的背景（什么主题）
2. Mike 聊了哪几个方向（只列主题，不给观点或结论）
3. 数字感：点出本场直播涵盖了几个核心话题、回答了几位朋友的提问等量化信息，强化「内容丰富」的感觉

语气亲切、轻松，像一个熟悉 Mike 内容的小编在帮你划重点。
不要用 Mike 第一人称，以小编第三方角度引出内容。

<good_example>Mike 本周加开了一场直播，聊了 3 个核心话题，还回答了 5 位朋友的连麦提问。这次他谈到了一个被严重低估的板块、大盘接下来的走向判断，还有一些实操层面的讨论。</good_example>
<bad_example>Mike 认为能源板块被低估，因为 AI 对电力需求很大，他看好核能方向。</bad_example>
</section>

<section name="CTA">
固定 CTA 文案，每封信都一样：
「想知道 Mike 怎么说？查看完整摘要 →」
导向 App 内该场直播的摘要页。
</section>

---

**## 模式 A：观众提问型（有 Q&A 时使用）**

在「本期直播聊了什么」之后，加入以下区块：

<section name="观众都在问什么">
从逐字稿中识别观众提问，尽量全部列出，只呈现问题本身，绝不透露 Mike 的回答。
选择标准：挑选其他用户也可能有同样疑问的问题，让读者产生「我也想知道答案」的感觉。
保留问题中的具体细节（含标的名称），越具体越能引起共鸣。

<good_example>
- OKLO 和 SMR 都是做小型核电的，资金有限只能选一个，怎么考虑？
- 现在才进场能源板块，还来得及吗？
</good_example>
<bad_example>
用户提问：OKLO 和 SMR 只能选一个怎么办？
Mike：我个人更偏重 OKLO，它的商业模式更像 AI 时代的电力印钞机。
（问题本身没问题，但绝不能附上 Mike 的回答）
</bad_example>
</section>

---

**## 模式 B：核心主题型（无 Q&A 时使用）**

在「本期直播聊了什么」之后，加入以下区块：

<section name="Mike 这场聊了哪些重点">
从逐字稿中提取 Mike 讨论的核心主题，以条列方式呈现。
只点出主题方向，绝不透露 Mike 的观点、判断或结论。
让读者看到「有这么多有料的话题」，但不知道 Mike 怎么说。

<good_example>
- 2026 年他最看好的一个板块方向
- 大盘短期走势的关键判断
- AI 对某个传统行业的冲击
- 一个大家忽略但他认为很重要的风险
</good_example>
<bad_example>
- Mike 认为能源板块最被低估
- 他判断大盘短期会回调 10%
- AI 会让电力需求暴增
（这些都透露了 Mike 的具体观点）
</bad_example>
</section>

</output_structure>

<output_format>
请用 markdown 格式输出。根据所选模式，使用对应的模板：

****模式 A（有 Q&A）：****
```
# {主旨行}

每周直播精华，小编帮你划重点 ✦

---

**📌 本期直播聊了什么**

{小编摘要，包含主题方向与数字感，2-3 句自然语言}

---

**🙋 观众都在问什么**

- {问题 1}
- {问题 2}
- {问题 3}
- ...（尽量列出所有识别到的观众提问）

---

[想知道 Mike 怎么说？查看完整摘要 →]({App 链接占位})

💡 打开 App，第一时间获取下次直播通知，精彩不错过。
```

****模式 B（无 Q&A）：****
```
# {主旨行}

每周直播精华，小编帮你划重点 ✦

---

**📌 本期直播聊了什么**

{小编摘要，包含主题方向与数字感，2-3 句自然语言}

---

**🔍 Mike 这场聊了哪些重点**

- {主题方向 1}
- {主题方向 2}
- {主题方向 3}
- ...

---

[想知道 Mike 怎么说？查看完整摘要 →]({App 链接占位})

💡 打开 App，第一时间获取下次直播通知，精彩不错过。
```

说明：
- 开头固定开场白「每周直播精华，小编帮你划重点 ✦」，每封信都一样
- 用分隔线（---）和小标题 emoji 明确区分各 section
- CTA 用 markdown 链接格式，链接部分用占位符
- 结尾固定模板「💡 打开 App，第一时间获取下次直播通知，精彩不错过。」，每封信都一样
</output_format>

<rules>
- 长度：控制在手机一屏可读完，整体约 150-200 字（不含固定开场白和固定结尾）
- 语言：简体中文
- 口吻：亲切轻松，像小编在帮你划重点
- 核心原则：只告诉用户「这场聊了什么主题、观众问了什么问题」，绝不透露任何观点、结论、答案。所有细节留给 App 内的完整摘要。
- 内容边界：观众提问中可以保留具体标的名称（这是问题的一部分），但 Mike 的观点、回答、判断、操作建议绝不出现。小编摘要和核心主题列表只点到板块/主题层级，不出现具体结论。
</rules>


""",
            
            ContentFormat.YT_POST: """

<role>
你是知名美股投资 YouTuber「Mike」的内容行销专家。
你的任务是将语音直播逐字稿提炼成一篇 YouTube 社群贴文，以 Mike 的第一人称口吻撰写。
目标是让 YouTube 粉丝对直播内容产生兴趣，进而下载 App 查看更完整的直播摘要。
</role>

<input>
一场语音直播的逐字稿（纯文字）。
</input>

<mike_voice>
Mike 的口吻特征：
- 真实且坦率：不讲虚的，直击投资痛点
- 幽默且有温度：把粉丝当朋友交流，会分享生活观察
- 专业但不傲慢：强调底层逻辑，而非盲目报明牌

<good_example>昨晚聊了一个我觉得大家都忽略的板块，直播间好几个朋友都说没想到，我花了不少时间把底层逻辑拆开来讲。</good_example>
<bad_example>昨晚的直播非常精彩，我分享了很多干货，大家反响热烈，一定不要错过！</bad_example>
</mike_voice>

<instructions>
在生成贴文之前，先判断逐字稿中是否存在观众互动段落，再选择对应的模式输出。

判断依据：
- 转述提问：出现「有人问」「这位朋友说」「你的问题是」「刚才有人提到」等表述
- 互动指令：出现「举手」「留言」「连麦」「上麦」等词汇后，紧接的内容通常是互动段落
- 回应性用语：「这个问题很好」「你说得对」「我来回答一下」「这位朋友讲得不错」
- 话题突然切换：从主线内容突然跳到一个具体的、非计划中的话题，通常是在回应观众

- 有 Q&A → 使用「模式 A：观众提问型」
- 无 Q&A → 使用「模式 B：核心主题型」

直接输出最终贴文，不需要输出判断过程。
</instructions>

<output_structure>
一篇简体中文 YouTube 社群贴文，以 Mike 第一人称撰写。根据判断结果，选择以下其中一种模式：

---

## 通用元素（两种模式共用）

<section name="开场 Hook">
根据逐字稿中 Mike 实际提到的信息营造直播热度，例如在线人数、时区分布、直播时长、讨论氛围等。
严格只使用逐字稿中出现过的信息，不要编造任何逐字稿中没有的内容，包括但不限于：
- 数据（人数、时长等）
- 互动形式（这个直播没有弹幕、没有留言板，只有举手连麦）
- 氛围描写（「疯狂提问」「刷屏」等逐字稿中没有的场景）
如果逐字稿中没有相关信息，就用其他方式自然带出「昨晚直播聊了不少东西」的感觉。
目的：营造「错过可惜」的氛围，但必须基于真实信息。

<good_example>昨晚临时加开了一场直播，没想到这么多朋友跨时区来听，聊到快两个小时才结束，好几个话题都讲得比预期深很多。</good_example>
<bad_example>昨晚直播在线人数达到 500 人，覆盖了 8 个时区！（逐字稿中未提及这些数据）</bad_example>
<bad_example>大家一边涌进直播间，一边在弹幕疯狂提问。（直播没有弹幕功能，且「疯狂提问」是编造的氛围描写）</bad_example>
</section>

<section name="结论金句">
从逐字稿中挑选一句最能总结这场直播精神的 Mike 原话，加引号呈现。
保留 Mike 原本的口语风格。
</section>

<section name="结尾导流">
在结论金句之后，用一句话轻松带到 App 免费社群，告知更详细的内容整理在那里。
语气像顺口一提，不要有推销感，根据当场直播主题自然衔接。

<good_example>如果你想了解更多关于 2026 年投资机会的讨论大纲，欢迎下载我的 App 并加入免费社群围观。</good_example>
<bad_example>赶快下载 App 加入社群，不要错过这次机会！（太像广告）</bad_example>
</section>

---

## 模式 A：观众提问型（有 Q&A 时使用）

在「开场 Hook」之后，依序加入以下区块：

<section name="Q&A 精华">
从逐字稿中挑选 1 个最有代表性的观众提问（非 Mike 自问自答）。
用弔胃口的方式给出 Mike 的想法方向，但不完整回答。
让读者感觉「有点意思但没讲完，想知道更多」。

<good_example>
有朋友问：OKLO 和 SMR 都是做小型核电的，资金有限只能选一个怎么办？

我的想法是，这两家虽然都做核电，但商业模式完全不一样，一个像是卖产品，一个更像是建平台收租。具体怎么选，我在直播里拆得很细，这里就不展开了。
</good_example>
<bad_example>
有朋友问 OKLO 和 SMR 怎么选？我更看好 OKLO，它的模式是自己建电站签 20 年订阅合同，未来现金流锁死，就像 AI 时代的电力印钞机。
（给得太完整，没有进 App 的动力）
</bad_example>
</section>

<section name="其他用户提问">
再列出 1-3 个观众提问，只呈现问题，不给任何观点或回答。
目的是让读者知道还有更多讨论的议题。
保留问题中的具体细节（含标的名称）。

<good_example>
昨晚还有几个朋友问了不错的问题：
- 现在才进场能源板块，还来得及吗？
- 美股券商开户政策各国不同，资金怎么分散比较安全？
- 核能 ETF 除了常见的那几档，还有什么选择？
</good_example>
</section>

---

## 模式 B：核心主题型（无 Q&A 时使用）

在「开场 Hook」之后，加入以下区块：

<section name="这场聊了哪些重点">
以 Mike 第一人称，列出这场直播讨论的核心主题方向。
只点出主题，不透露观点、判断或结论。
让读者看到话题丰富，但不知道 Mike 怎么说。

<good_example>
昨晚主要聊了这几个方向：
- 2026 年我最看好的一个板块
- 大盘接下来的走势判断
- AI 对一个传统行业的冲击，很多人还没注意到
- 一个大家容易忽略但我觉得很重要的风险
</good_example>
<bad_example>
昨晚聊了能源板块，我认为被严重低估，因为 AI 会推动电力需求暴增。
（直接透露了观点和结论）
</bad_example>
</section>

</output_structure>

<output_format>
请用纯文本格式输出，不使用任何 icon 或 emoji。段落之间用空行分隔。

**模式 A（有 Q&A）：**
```
{开场 Hook}

{Q&A 精华：一个问题 + 弔胃口的不完整回答}

昨晚还有几个朋友问了不错的问题：
- {问题 1}
- {问题 2}
- {问题 3}

"{结论金句}"

{结尾导流：一句话轻松带到 App 免费社群}
```

**模式 B（无 Q&A）：**
```
{开场 Hook}

昨晚主要聊了这几个方向：
- {主题方向 1}
- {主题方向 2}
- {主题方向 3}
- ...

"{结论金句}"

{结尾导流：一句话轻松带到 App 免费社群有更丰富的内容}
```
</output_format>

<rules>
- 语言：简体中文
- 口吻：Mike 第一人称，像在跟粉丝朋友聊天
- 不使用任何 icon、emoji 或 markdown 格式（YouTube 社群贴文不支持 markdown）
- 核心原则：给一点甜头建立兴趣，但留住关键内容驱动用户下载 App
- 内容边界：Q&A 精华可以给想法方向但不给完整答案，其他提问只列问题不给回答，结论金句是唯一可以直接引用 Mike 观点的地方
- 不要编造逐字稿中没有的信息
</rules>


""",
            
            ContentFormat.SUMMARY: """

這是我一場語音直播的逐字稿，幫我做一個精簡的總結，長度不超過500字
已列點方式呈現，呈現3個最重要的點就好，不能多也不能少，但每一點需要有以下標準:

1. 可以一眼看懂的標題
2. 具體、有含金量的內文
3. 每點字數不超過100字
4. 不用有多餘的文字說明，只要呈現標題和內文就好
5. 輸出用簡體中文

逐字稿內容：
{transcript}

""",
            
            ContentFormat.SUBSTACK_ARTICLE: """
<role>
你是知名美股投资 YouTuber「Mike」的深度内容编辑。
你的任务是将一场语音直播的逐字稿，转化为一篇结构清晰、观点完整的深度文章，以 Mike 的第一人称撰写。
这篇文章是付费会员专属内容，等同于直播回放的「文字精华版」，让没时间听完整回放的会员也能快速掌握所有干货。
核心原则：去噪不去人味，重组不失原意。
</role>

<input>
一场语音直播的逐字稿（纯文字）。
</input>

<mike_voice>
这篇文章要读起来像 Mike 坐下来认真写的专栏，而不是一份冷冰冰的分析报告。

保留的元素：
- Mike 的比喻和举例方式（例如用生活观察类比投资逻辑）
- 直白、毒舌的风格（例如对市场噪音或散户心态的犀利点评）
- 口语化的句式和节奏感（「就直接说」「拆开来讲」「这个很关键」）
- 个人经历的分享（线下见面、自己账户的表现、旅行见闻等，只要跟主题相关）

去掉的元素：
- 无意义的语气词和填充词（「呃」「就是说」「然后呢」「对吧」）
- 同一观点的重复表述（直播中常见的反复强调，文章中只保留最精炼的一次）
- 直播场景专属的互动语（「听得到吗」「刚进来的朋友」「可以举手」「我们连麦聊一下」）
- 跟主题完全无关的闲聊

<example context="逐字稿原文">那今天咱们就说2026年我最看好的板块就是能源。为什么看好这个板块？我说一下底层逻辑。</example>
<example context="文章输出">今天就直接说，2026 年我最看好的板块就是能源。为什么？我来说一下底层逻辑。</example>
</mike_voice>

<instructions>
将逐字稿转化为深度文章，按以下步骤处理：

第一步：通读逐字稿，识别所有主题
- 梳理整场直播讨论到的所有主题
- 标记哪些内容属于同一主题（即使它们散落在直播的不同时间点）
- 包括 Mike 的主讲内容和观众互动中产生的讨论，一视同仁

第二步：决定章节结构
- 按主题逻辑排序，而非直播的时间顺序
- 相关内容归拢到同一章节，让每个主题的讨论完整呈现
- 章节数量不硬限制，由内容丰富度决定

第三步：逐章节撰写
- 去噪但保留 Mike 的语感和人味
- 观点、具体标的分析、操作思路完整呈现，不需要保留或隐藏任何内容
- 每个章节有清晰的小标题，段落之间有自然的过渡

第四步：补上标题、导言、结语
- 标题从核心主题中提炼，有观点感但不标题党
- 导言直接从主题切入，让读者知道接下来会看到什么
- 结语收束整场讨论，可以是 Mike 的总结性观点或行动建议

直接输出最终文章，不需要输出处理过程。
</instructions>

<output_structure>
一篇简体中文深度文章，以 Mike 第一人称撰写。

<section name="标题">
从直播核心主题中提炼，风格类似 Substack 投资专栏标题。
有观点方向，但不夸张、不标题党。

<good_example>2026 年我最看好能源板块的底层逻辑</good_example>
<good_example>为什么我说 2026 是赚钱机会最大、也最危险的一年</good_example>
<bad_example>震惊！Mike 揭秘 2026 年暴富密码！</bad_example>
<bad_example>Mike 直播回顾（暴露了内容来源是直播）</bad_example>
</section>

<section name="导言">
1-2 段，自然地带入主题。
让读者快速建立预期：这篇文章会聊什么、为什么值得读。
语气像 Mike 在文章开头跟你打个招呼，直接切入主题。
不要提到直播、不要交代「为什么写这篇文章」，直接从主题本身出发。

<good_example>最近发生了几件事，我觉得有必要跟大家聊一下。今天主要说说能源板块的机会、大盘走势的判断，还有一些大家关心的个股问题。</good_example>
<bad_example>这周临时加开了一场直播，因为最近市场波动比较大。（暴露了内容来自直播）</bad_example>
</section>

<section name="正文主体">
按主题分章节，每个章节包含：
- 清晰的小标题
- Mike 的完整观点和分析逻辑
- 具体标的、数据、案例（如果逐字稿中有提到）
- 自然的段落过渡

章节数量由内容决定，不硬限制。
观众提问和 Mike 的回答，如果跟某个主题相关，自然融入该章节；如果是独立的话题，可以单独成为一个章节。
</section>

<section name="结语">
1-2 段，收束整场讨论。
可以是 Mike 对当前市场的总结性看法，或是给读者的行动建议。
语气像 Mike 在文章结尾做个收尾，不需要刻意煽情或喊口号。

<good_example>总的来说，2026 年的机会很大，但波动也不会小。保持耐心，控制好仓位，把每次回调当成机会而不是恐慌的理由。</good_example>
</section>
</output_structure>

<output_format>
使用 markdown 格式输出：

```
# {标题}

{导言：1-2 段}

## {章节一小标题}

{内容}

## {章节二小标题}

{内容}

## {章节三小标题}

{内容}

...（章节数量由内容决定）

---

{结语：1-2 段}
```
</output_format>

<rules>
- 长度：约 3000-5000 字，视直播内容的丰富程度弹性调整，重点是把干货覆盖到，不硬凑也不硬砍
- 语言：简体中文
- 口吻：Mike 第一人称，口语化但经过轻度书面化修饰，保留个人风格和人味
- 内容边界：全开放，包括具体股票代号、ETF 名称、买卖时机、仓位建议等，完整呈现 Mike 的所有观点
- 结构原则：按主题逻辑组织，不按直播时间顺序，相关内容归拢在一起
- 不要编造逐字稿中没有的信息、数据或观点
- 不要添加 Mike 没有表达过的观点或分析
- 如果逐字稿中某段内容跟任何主题都无关（纯闲聊、技术问题等），直接省略
- 严禁出现「直播」「这场直播」「直播里」「上次直播」等任何暴露内容来源是直播的字眼。文章应该读起来就是一篇独立的专栏文章，读者不需要知道素材来自直播
</rules>


"""
        }
        
        # 取得對應格式的基礎提示詞模板（不再使用 str.format，以避免與模板中其他 {欄位} 衝突）
        template = templates.get(format_type, "")
        
        # 說明：
        # - 模板中只有 {transcript} 這個佔位符需要被實際替換成逐字稿內容
        # - 其他像 {標題}、{小標題} 等只是給模型看的示意結構，因此不應該被 Python 當成變數解析
        # - 使用 replace 只針對 {transcript} 做替換，保留其餘大括號原樣，避免 KeyError 等問題
        full_prompt = template.replace("{transcript}", transcript)
        
        return full_prompt
    
    def _call_llm(self, prompt: str, format_type: ContentFormat = None) -> str:
        """
        調用 LLM API 生成內容
        
        Args:
            prompt: 提示詞
            format_type: 文案格式類型（用於動態調整 max_tokens）
            
        Returns:
            str: 生成的內容
        """
        system_prompt = "你是一個專業的內容編輯和文案撰寫專家，擅長將語音直播內容轉換為各種形式的文案。"
        
        # 根據格式類型動態調整 max_tokens
        # Substack 長文需要 3000-5000 字，需要更多 tokens
        if format_type == ContentFormat.SUBSTACK_ARTICLE:
            max_tokens = 8000  # Substack 長文需要更多 tokens
        else:
            max_tokens = 2000  # 其他格式維持原本的設定
        
        if self.provider == "openai":
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content.strip()
        
        elif self.provider == "anthropic":
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text.strip()
        
        elif self.provider == "gemini":
            # Gemini API 使用方式
            model = self.client.GenerativeModel(self.model)
            
            # 組合系統提示詞和使用者提示詞
            full_prompt = f"{system_prompt}\n\n{prompt}"
            
            response = model.generate_content(
                full_prompt,
                generation_config={
                    "temperature": 0.7,
                    "max_output_tokens": max_tokens,
                }
            )
            return response.text.strip()
        
        else:
            raise ValueError(f"不支援的 LLM 提供者: {self.provider}")
    
    def _save_content(self, file_id: str, format_type: ContentFormat, content: str) -> str:
        """
        儲存生成的文案內容
        
        Args:
            file_id: 檔案 ID
            format_type: 文案格式類型
            content: 文案內容
            
        Returns:
            str: 儲存的檔案路徑
        """
        # 根據格式類型決定副檔名
        extensions = {
            ContentFormat.COMMUNITY_POST: "_community_post.txt",
            ContentFormat.EMAIL: "_email.txt",
            ContentFormat.YT_POST: "_yt_post.txt",
            ContentFormat.SUMMARY: "_summary.txt",
            ContentFormat.SUBSTACK_ARTICLE: "_substack_article.txt"
        }
        
        extension = extensions.get(format_type, ".txt")
        output_path = get_output_path(file_id, extension)
        
        # 儲存內容
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return output_path


# 建立全域服務實例（單例模式）
_content_generator = None

def get_content_generator() -> ContentGenerator:
    """
    取得文案生成服務實例（單例模式）
    
    Returns:
        ContentGenerator: 服務實例
    """
    global _content_generator
    if _content_generator is None:
        _content_generator = ContentGenerator()
    return _content_generator
