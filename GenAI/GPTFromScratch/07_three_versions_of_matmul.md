Excellent! **This is the beginning of Self-Attention.** In fact, many people think attention starts with the Query, Key, and Value matrices, but **Karpathy is first building the intuition**.

This entire code cell answers one question:

> **"How can every token collect information from all the previous tokens?"**

He shows **three different implementations** that all produce **exactly the same result**:

1. Using Python loops (easy to understand)
2. Using matrix multiplication (fast)
3. Using Softmax (this becomes Self-Attention)

The idea stays the same. Only the implementation changes.

---

# The Goal of this Cell

Look at this comment:

```python
# We want x[b,t] = mean_{i<=t} x[b,i]
```

This one line explains the entire cell.

Let's decode it.

```
x[b,t]
```

means

> Take

* batch **b**
* token **t**

Example:

```
x[2,5]
```

means

```
Batch 2

Token 5
```

---

Now look at

```
mean(i <= t)
```

This means

> Take the average of

```
Token0

Token1

...

Token t
```

In other words,

**Every token wants to know the average of all previous tokens (including itself).**

---

## Why do we want this?

Imagine the sentence

```
I
love
Python
very
much
```

Suppose we're currently processing

```
very
```

Should "very" know only about itself?

No.

It should also know

```
I

love

Python
```

because those words give context.

This is exactly the idea behind Attention.

---

# Step 1

```python
torch.manual_seed(1337)
```

Just fixes the random numbers.

Nothing new.

---

# Step 2

```python
B,T,C = 4,8,2
```

Let's understand these three variables.

```
B = Batch Size
```

We already know this.

```
4 sequences
```

---

```
T = Time
```

Time simply means

```
Sequence Length
```

So

```
8 tokens
```

per sequence.

---

```
C = Channels
```

This is new.

What is a channel?

Think of it as

> **Features describing each token.**

Earlier

our token was represented by

```
65 logits
```

Later

it'll become

```
384 numbers

768 numbers

1024 numbers
```

Here

Karpathy keeps it tiny.

```
2 features
```

so we can visualize everything.

---

# Visualizing x

```python
x = torch.randn(B,T,C)
```

Shape

```
(4,8,2)
```

Let's open it.

```
Batch1

Token1

[1.2 , -0.4]

Token2

[0.7 , 2.1]

...

Token8

[-0.3 , 0.9]
```

Every token has

```
2 numbers
```

Think of each token as a point in 2D space.

---

# Shape

```
(4,8,2)
```

means

```
4 sequences

↓

each has

↓

8 tokens

↓

each token has

↓

2 features
```

---

# Version 1

Now comes the easiest implementation.

```python
xbow = torch.zeros((B,T,C))
```

Creates

```
(4,8,2)
```

filled with zeros.

This will store the answers.

---

# Outer Loop

```python
for b in range(B):
```

This means

```
Process Batch1

↓

Process Batch2

↓

Process Batch3

↓

Process Batch4
```

---

# Inner Loop

```python
for t in range(T):
```

This means

```
Token0

↓

Token1

↓

Token2

...

↓

Token7
```

---

So together

```
for b

    for t
```

means

```
For every token

inside every batch
```

---

# This Line

```python
xprev = x[b,:t+1]
```

This is the heart of Version 1.

Let's understand it.

Suppose

```
t = 4
```

Then

```python
:t+1
```

becomes

```python
:5
```

So

```python
x[b,:5]
```

means

Take

```
Token0

Token1

Token2

Token3

Token4
```

Notice

It **does not include future tokens**.

Exactly what GPT needs.

---

Suppose

Current sequence

```
I

love

Python

very

much

today

!
```

If

```
t=3
```

Current word

```
very
```

Then

```
xprev
```

contains

```
I

love

Python

very
```

Not

```
much

today

!
```

because those are future words.

---

# Shape of xprev

Suppose

```
t=5
```

Then

```
6 tokens
```

Each token

```
2 features
```

Shape

```
(6,2)
```

Generally,

when you're at token `t`, `xprev` has shape:

```
(t+1, C)
```

because you're taking tokens `0` through `t` (inclusive), and each token has `C` features.

---

# Average

```python
torch.mean(xprev,0)
```

This line says

Take the mean

along

```
dimension 0
```

Remember

```
xprev

(6,2)
```

Example

```
[
 [2 4]
 [6 8]
 [1 5]
]
```

Mean of first column

```
(2+6+1)/3

=

3
```

Mean of second column

```
(4+8+5)/3

=

5.67
```

Result

```
[3 ,5.67]
```

Shape

```
(2)
```

One averaged feature vector.

---

# Store It

```python
xbow[b,t]
```

gets

```
Average of

all previous tokens

including itself
```

---

Let's visualize one sequence.

Suppose

```
Token0

[1,2]
```

Token1

```
[3,4]
```

Token2

```
[8,6]
```

---

For

```
t=0
```

Average

```
[1,2]
```

---

For

```
t=1
```

Average

```
([1,2]+[3,4])/2

=

[2,3]
```

---

For

```
t=2
```

Average

```
([1,2]+[3,4]+[8,6])/3

=

[4,4]
```

Notice

Every token becomes

```
Average of previous tokens.
```

---

# Why is this slow?

Look at the loops.

```
Batch

↓

Token

↓

Slice

↓

Mean
```

Imagine GPT

```
Batch

64

Tokens

1024
```

That's

```
64 ×1024

=

65536

iterations
```

Too slow.

Deep learning avoids Python loops whenever possible.

---

# Version 2

Now Karpathy says

Let's remove the loops.

```python
wei = torch.tril(torch.ones(T,T))
```

With

```
T=8
```

we get

```
8×8
```

Lower triangular matrix.

```
1 0 0 0 ...

1 1 0 0 ...

1 1 1 0 ...

...
```

Exactly like previous cell.

---

Normalize

```python
wei = wei / wei.sum(1,keepdim=True)
```

Now

every row

adds to

```
1
```

Example

```
[
[1,0,0]

[0.5,0.5,0]

[1/3,1/3,1/3]
]
```

This is a matrix of averaging weights.

---

# Matrix Multiplication

```python
xbow2 = wei @ x
```

This is the magical line.

Let's inspect the shapes:

* `wei` has shape `(T, T)` → `(8, 8)`
* `x` has shape `(B, T, C)` → `(4, 8, 2)`

PyTorch automatically applies the same `(8,8)` weight matrix to **each batch independently**.

So conceptually, it does:

```text
Batch 1:
(8×8) @ (8×2) → (8×2)

Batch 2:
(8×8) @ (8×2) → (8×2)

Batch 3:
(8×8) @ (8×2) → (8×2)

Batch 4:
(8×8) @ (8×2) → (8×2)
```

The final output shape is:

```
(4,8,2)
```

Exactly the same as `xbow`.

Each row of `wei` computes the average of all previous token feature vectors.

---

# Check

```python
torch.allclose(xbow,xbow2)
```

returns

```
True
```

Meaning

```
Loop version

=

Matrix multiplication version
```

Exactly identical.

---

# Version 3

Now comes the brilliant part.

Instead of manually creating

```
1

0.5

1/3
```

Karpathy builds them using

**Softmax**.

---

First

```python
tril = torch.tril(torch.ones(T,T))
```

Same lower triangular matrix.

---

Next

```python
wei = torch.zeros((T,T))
```

Creates

```
8×8
```

of zeros.

---

Then

```python
wei = wei.masked_fill(tril==0,float('-inf'))
```

This line is very important.

Initially

```
0 0 0

0 0 0

0 0 0
```

After masking

```
0   -∞   -∞

0    0   -∞

0    0    0
```

Why?

Future positions become

```
−∞
```

---

Now

Softmax

```python
wei = F.softmax(wei,dim=-1)
```

Let's compute one row.

Suppose

```
[0,-∞,-∞]
```

Softmax

becomes

```
[1,0,0]
```

---

Second row

```
[0,0,-∞]
```

Softmax

```
exp(0)=1

exp(0)=1

exp(-∞)=0
```

Normalize

```
[0.5,0.5,0]
```

---

Third row

```
[0,0,0]
```

Softmax

```
[1/3

1/3

1/3]
```

Amazing!

We recreated exactly the same averaging matrix **without manually dividing**.

---

Then

```python
xbow3 = wei @ x
```

Again

weighted average.

---

Finally

```python
torch.allclose(xbow,xbow3)
```

returns

```
True
```

All three versions produce the same output.

---

# Why introduce Softmax?

This is the bridge to **Self-Attention**.

In Version 2, the weights were **fixed**:

```text
[0.5, 0.5, 0]
```

In the Transformer, those weights are **learned from the input**.

For one sentence, the weights might become:

```text
[0.1, 0.8, 0.1]
```

For another sentence:

```text
[0.7, 0.2, 0.1]
```

Softmax converts arbitrary scores into valid probabilities that sum to 1, making them perfect attention weights.

---

# The Evolution Across the Three Versions

```
Version 1
──────────
Python Loops

Take previous tokens

↓

Compute average manually

↓

Very slow
```

↓

```
Version 2
──────────
Matrix Multiplication

Take previous tokens

↓

Weighted average

↓

Fast
```

↓

```
Version 3
──────────
Softmax

Create weights automatically

↓

Weighted average

↓

This becomes Self-Attention
```

## The most important insight from this cell

Notice that **the output is not changing**—only **how we compute it** changes.

All three versions answer the same question:

> **"How should each token combine information from all previous tokens?"**

The progression is:

1. **Loops** → easiest to understand.
2. **Matrix multiplication** → efficient implementation.
3. **Softmax** → the same mechanism used by Transformers.


