# 强化学习 (RL) 学习路径

## 第一部分：核心概念入门

### 1.1 什么是强化学习？

强化学习是一种**通过试错来学习**的机器学习范式。

**核心思想**：
- 一个**智能体 (Agent)** 在**环境 (Environment)** 中行动
- 每个行动会产生**奖励 (Reward)** 信号
- 目标是学习一个**策略 (Policy)**，最大化长期累积奖励

**类比理解**：
> 就像训练狗狗：做对了给零食（正奖励），做错了不给（负奖励）。狗狗通过多次尝试，学会哪些行为能获得更多零食。

### 1.2 五大核心要素

| 要素 | 符号 | 说明 | 例子（下棋） |
|------|------|------|-------------|
| **状态** | `s` | 环境的当前情况 | 棋盘上棋子的位置 |
| **动作** | `a` | 智能体可以做的选择 | 移动某个棋子到某个位置 |
| **奖励** | `r` | 行动的即时反馈 | 吃掉对方棋子 +10，被将棋 -100 |
| **策略** | `π` | 从状态到动作的映射 | "看到这个棋形，我应该走这一步" |
| **价值** | `V(s)` | 状态的长期好坏 | "这个棋形最终赢的概率有多大" |

### 1.3 关键概念

#### 马尔可夫决策过程 (MDP)
强化学习的数学框架，假设**当前状态包含所有历史信息**：
```
P(s'|s, a) = 下一步是 s' 的概率，给定当前状态 s 和动作 a
```

#### 折扣回报 (Discounted Return)
```
G_t = r_t + γ*r_{t+1} + γ²*r_{t+2} + ...
```
- `γ` (gamma) 是折扣因子 (0~1)
- 越远的奖励权重越低
- 体现"落袋为安"的思想

#### 价值函数 vs 策略函数
- **价值函数 V(s)**: 评估状态好坏（"这个局面值多少"）
- **策略函数 π(a|s)**: 决定行动（"在这个局面该走哪步"）

---

## 第二部分：经典算法详解

### 2.1 Q-Learning (值函数方法)

**核心思想**：学习一个 Q 表，记录每个 (状态，动作) 对的长期价值。

**Q 值更新公式**：
```
Q(s, a) ← Q(s, a) + α * [r + γ * max(Q(s', a')) - Q(s, a)]
```

**直观理解**：
- `Q(s, a)`: 当前估计的 (状态 s, 动作 a) 的价值
- `r + γ * max(Q(s', a'))`: 实际观察到的价值（即时奖励 + 未来最佳价值）
- `α`: 学习率，决定更新速度

**伪代码**：
```
初始化 Q 表（所有值为 0）
for 每个 episode:
    初始化状态 s
    while 未结束:
        用 ε-greedy 策略选择动作 a  # 大部分时间选最佳，偶尔随机探索
        执行动作 a，观察奖励 r 和新状态 s'
        Q(s, a) ← Q(s, a) + α * [r + γ * max(Q(s', *)) - Q(s, a)]
        s ← s'
```

### 2.2 Deep Q-Network (DQN)

**问题**：Q-Learning 需要存储 Q 表，状态空间大时不可行。

**解决方案**：用神经网络近似 Q 函数。

```
Q(s, a; θ) ≈ 神经网络输出，参数为 θ
```

**关键创新**：
1. **经验回放 (Experience Replay)**: 存储历史经验，随机采样打破相关性
2. **目标网络 (Target Network)**: 用独立的网络计算目标值，稳定训练

**损失函数**：
```
L(θ) = E[(r + γ * max(Q(s', a'; θ')) - Q(s, a; θ))²]
```

### 2.3 Policy Gradient (策略梯度)

**核心思想**：直接优化策略，而不是通过价值函数间接学习。

**策略梯度定理**：
```
∇J(θ) = E[∇log π(a|s; θ) * Q(s, a)]
```

**直观理解**：
- 如果某个动作带来了高奖励，增加它的概率
- 如果某个动作带来了低奖励，减少它的概率

**REINFORCE 算法**：
```
for 每个 episode:
    用当前策略 π 收集轨迹 {(s_t, a_t, r_t)}
    计算每个时刻的回报 G_t
    更新参数：θ ← θ + α * Σ ∇log π(a_t|s_t) * G_t
```

### 2.4 PPO (Proximal Policy Optimization)

**问题**：策略梯度方法训练不稳定，步长难控制。

**PPO 的解决方案**：限制策略更新的幅度。

**裁剪目标函数**：
```
L_CLIP(θ) = E[min(r_t * A_t, clip(r_t, 1-ε, 1+ε) * A_t)]
```
其中 `r_t = π_θ(a|s) / π_old(a|s)` 是策略比率

**直观理解**：
- 如果新策略和旧策略差别太大，就限制更新幅度
- 保证训练稳定，不会"走偏"

---

## 第三部分：与 RAG 系统的结合

### 3.1 问题建模

**场景**：代理需要通过 RAG 系统查找知识，完成复杂任务。

**MDP 定义**：

| 要素 | 定义 |
|------|------|
| **状态 s** | (用户查询，历史对话，已检索的文档，当前任务进度) |
| **动作 a** | {`search(query)`, `read(doc_id)`, `summarize()`, `answer()`, `ask_clarification()`} |
| **奖励 r** | +10 完成任务，+1 找到相关信息，-1 每步消耗，-5 错误答案 |
| **策略 π** | 根据当前状态选择最佳动作的神经网络 |

### 3.2 状态表示设计

```python
# 状态向量 = 各部分编码的拼接
state = [
    query_embedding,      # 用户查询的向量表示
    history_embedding,    # 对话历史的向量表示
    retrieved_docs,       # 已检索文档的 ID 列表（one-hot 或 embedding）
    task_progress,        # 任务进度（0~1 的标量）
]
```

### 3.3 动作空间设计

**离散动作空间**（适合 DQN）：
```
0: search - 发起新的搜索
1: read - 阅读已检索的文档
2: summarize - 总结已有信息
3: answer - 给出最终答案
4: ask_clarification - 请求用户澄清
```

**参数化动作**（适合 PPO）：
```
(search, query="xxx")
(read, doc_id=123)
(answer, text="xxx")
```

### 3.4 奖励函数设计

```python
def calculate_reward(action, state, result):
    reward = 0
    
    # 任务完成奖励
    if task_completed:
        reward += 10
    
    # 信息质量奖励（需要评估检索结果的相关性）
    if action == "search" and result.relevance > 0.7:
        reward += 1
    
    # 效率惩罚（鼓励快速完成任务）
    reward -= 0.1  # 每步消耗
    
    # 错误惩罚
    if action == "answer" and answer_is_wrong:
        reward -= 5
    
    return reward
```

---

## 第四部分：实践建议

### 4.1 学习资源

**入门教程**：
- [Spinning Up in Deep RL](https://spinningup.openai.com/) - OpenAI 官方教程
- [Deep Reinforcement Learning Course](https://haromao.dev/) - 交互式教程

**经典书籍**：
- 《Reinforcement Learning: An Introduction》(Sutton & Barto) - RL 领域的"圣经"

**代码库**：
- [Stable Baselines3](https://stable-baselines3.readthedocs.io/) - 现成的 RL 算法实现
- [RLlib](https://docs.ray.io/en/latest/rllib/index.html) - 大规模 RL 框架

### 4.2 最小可行实验

**建议从简单的环境开始**：

1. **GridWorld** - 网格世界，最基础的 RL 环境
2. **CartPole** - 平衡杆，经典基准任务
3. **自定义问答环境** - 简化版的 RAG-RL 任务

**实验步骤**：
```
1. 用 Stable Baselines3 实现 DQN
2. 在 CartPole 上验证算法正确性
3. 设计简化的 RAG-RL 环境（如：固定文档库的问答）
4. 逐步增加复杂度
```

### 4.3 代码模板

```python
# 自定义 RL 环境
import gymnasium as gym
from gymnasium import spaces
import numpy as np

class RAGEnv(gym.Env):
    def __init__(self, document_store):
        super().__init__()
        self.doc_store = document_store
        
        # 动作空间：5 个离散动作
        self.action_space = spaces.Discrete(5)
        
        # 状态空间：128 维向量
        self.observation_space = spaces.Box(
            low=-1, high=1, shape=(128,), dtype=np.float32
        )
    
    def reset(self):
        # 重置环境，返回初始状态
        self.current_query = random_query()
        self.retrieved_docs = []
        self.step_count = 0
        return self._encode_state(), {}
    
    def step(self, action):
        # 执行动作，返回 (新状态，奖励，是否结束，是否截断，信息)
        self.step_count += 1
        
        if action == 0:  # search
            new_docs = self.doc_store.search(self.current_query)
            self.retrieved_docs.extend(new_docs)
            reward = self._evaluate_relevance(new_docs)
        
        elif action == 3:  # answer
            reward = self._evaluate_answer()
            done = True
        
        else:
            reward = -0.1  # 其他动作的小惩罚
        
        return self._encode_state(), reward, done, False, {}
    
    def _encode_state(self):
        # 将当前状态编码为向量
        state = np.zeros(128)
        # ... 填充状态向量
        return state
```

---

## 第五部分：下一步行动

1. **安装依赖**：
   ```bash
   pip install gymnasium stable-baselines3 torch
   ```

2. **运行第一个示例**：
   ```python
   from stable_baselines3 import DQN
   env = gym.make("CartPole-v1")
   model = DQN("MlpPolicy", env, verbose=1)
   model.learn(total_timesteps=10000)
   ```

3. **设计你的第一个 RAG-RL 任务**：
   - 选择一个简单的文档库（如：10 篇技术文章）
   - 定义 5-10 个问答任务
   - 实现简化的环境

---

## 附录：术语对照表

| 英文 | 中文 | 说明 |
|------|------|------|
| Agent | 智能体 | 做决策的主体 |
| Environment | 环境 | 智能体交互的外部世界 |
| State | 状态 | 环境的当前情况 |
| Action | 动作 | 智能体可以做的选择 |
| Reward | 奖励 | 行动的即时反馈 |
| Policy | 策略 | 从状态到动作的映射规则 |
| Value | 价值 | 状态的长期期望回报 |
| Q-value | Q 值 | (状态，动作) 对的长期价值 |
| Episode | 回合 | 从开始到结束的完整交互序列 |
| Exploration | 探索 | 尝试新动作以发现更好策略 |
| Exploitation | 利用 | 使用已知最佳动作 |
