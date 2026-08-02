Let's go back to the sentence:

```text
I love learning Python because it is powerful.
```

Suppose the current word is

```text
it
```

How does the model know that **"it" refers to "Python"** and not "learning"?

The model needs to decide

> **Which previous words are important for me?**

This process is called **Attention**.

---

# What is Self-Attention?

Let's imagine four friends are discussing a project.

```text
Alice
Bob
Charlie
David
```

Suppose Bob wants to answer a question.

Before answering, Bob thinks

```text
Should I listen to Alice?

Should I listen to Charlie?

Should I listen to David?

Or should I trust myself?
```

He gives different importance to everyone.

For example

```text
Alice     10%

Bob        20%

Charlie    60%

David      10%
```

Then Bob combines everyone's ideas.

That is exactly what Self-Attention does.

Every token asks

> **"Which other tokens should I pay attention to?"**

---

# Overall Flow of this Cell

Before diving into the code, let's see the big picture.

```text
Input Tokens (x)
       │
       ▼
Create Keys
       │
       ▼
Create Queries
       │
       ▼
Compare Query with Every Key
       │
       ▼
Attention Scores
       │
       ▼
Softmax
       │
       ▼
Attention Weights
       │
       ▼
Create Values
       │
       ▼
Weighted Sum of Values
       │
       ▼
Output
```

Everything in this cell fits into this pipeline.

---

# Step 1

```python
torch.manual_seed(1337)
```

Nothing new.

It simply makes the random numbers reproducible.

---

# Step 2

```python
B,T,C = 4,8,32
```

Let's understand every variable.

```text
B = Batch Size
```

```text
4 sequences
```

---

```text
T = Time
```

Means

```text
Sequence Length
```

So

```text
8 tokens
```

---

```text
C = Channels
```

This means

```text
Embedding Dimension
```

Earlier

```text
C = 2
```

Now

```text
C = 32
```

Each token is represented by

```text
32 numbers
```

instead of just 2.

---

# Step 3

```python
x = torch.randn(B,T,C)
```

Shape

```text
(4,8,32)
```

Let's visualize one batch.

```text
Batch 1

Token1

[0.2
 -1.3
 ...
32 numbers]

Token2

[...]

...

Token8
```

Each token is now a vector of length 32.

Think of these 32 numbers as describing the token.

---

# Why do we need 32 numbers?

Imagine describing a person.

Instead of saying

```text
Height
```

you describe

```text
Height

Weight

Age

Hair Color

Eye Color

Profession

...

32 properties
```

Similarly,

each token has

```text
32 learned features.
```

---

# Single Head

```python
head_size = 16
```

This introduces a new concept.

Instead of looking at all

```text
32 features
```

this attention head will only work with

```text
16 features
```

Why?

Because later

multiple heads

look at different aspects of the sentence.

For now

we use

```text
One Head
```

---

# Linear Layers

Now comes

```python
key = nn.Linear(C, head_size, bias=False)
query = nn.Linear(C, head_size, bias=False)
value = nn.Linear(C, head_size, bias=False)
```

This is where most beginners get confused.

Let's understand why we need

* Key
* Query
* Value

---

# Imagine a Library

Suppose you walk into a huge library.

You ask

```text
I want a Python book.
```

How does the librarian find it?

Every book has

```text
Title

Category

Author
```

The librarian compares

```text
Your Request

↓

Book Labels
```

If they match,

you get the book.

Self-attention works exactly like that.

---

Each token creates

```text
Query

"What am I looking for?"
```

Key

```text
"What information do I have?"
```

Value

```text
"The actual information I carry."
```

---

Think of it like people.

Suppose every person has

## Query

```text
What do I need?
```

## Key

```text
What can I offer?
```

## Value

```text
Actual knowledge
```

Attention first matches

```text
Query

↓

Key
```

Then collects

```text
Value
```

Notice something very important:

> **The Key is NOT the information itself.**
>
> It is only a label used to determine whether another token should pay attention.
>
> The **Value** is the actual information that gets passed forward.

---

# What is nn.Linear?

Suppose

our token is

```text
32 numbers
```

Example

```text
[2
5
7
...
32 numbers]
```

The Linear layer converts it into

```text
16 numbers
```

Think of it like

```text
32 Features

↓

Projection

↓

16 Features
```

---

Internally

PyTorch creates

a matrix.

```text
32 ×16
```

Every token gets multiplied

by that matrix.

Result

```text
16 numbers
```

---

# Keys

```python
k = key(x)
```

Input

```text
(4,8,32)
```

Output

```text
(4,8,16)
```

Nothing mysterious happened.

Every token

went from

```text
32 features

↓

16 features
```

---

# Queries

```python
q = query(x)
```

Exactly the same.

Output

```text
(4,8,16)
```

But

different weights.

So

Keys

and

Queries

contain

different information.

---

# Visualizing

Suppose

Original token

```text
Python

↓

32 features
```

Key projection

```text
[0.2
1.3
...
16 numbers]
```

Query projection

```text
[-1.2
0.7
...
16 numbers]
```

Different vectors.

---

# This Line

Now comes

the heart of Self-Attention.

```python
wei = q @ k.transpose(-2,-1)
```

Let's understand it very carefully.

---

## Shapes

Queries

```text
(4,8,16)
```

Keys

```text
(4,8,16)
```

---

First

```python
k.transpose(-2,-1)
```

changes

```text
(4,8,16)

↓

(4,16,8)
```

Only the last two dimensions are swapped.

Think of one batch:

Before transpose:

```text
8 tokens × 16 features
```

After transpose:

```text
16 features × 8 tokens
```

This rearrangement is necessary so that matrix multiplication can compare every query with every key.

---

Now multiply

```text
(8×16)

@

(16×8)

↓

(8×8)
```

Since there are 4 batches,

overall shape

```text
(4,8,8)
```

---

# What does this multiplication mean?

This is NOT ordinary averaging anymore.

Every entry

```text
wei[i,j]
```

means

> **How much should token i pay attention to token j?**

This is extremely important.

Example

```text
        Token0 Token1 Token2

Token0   3.2    0.1    2.5

Token1   1.4    4.8    0.3

Token2   0.5    0.9    2.2
```

These numbers are called

```text
Attention Scores
```

Large number

↓

Very important.

Small number

↓

Not important.

---

# Why does `q @ kᵀ` give similarity?

Remember from linear algebra:

The **dot product** between two vectors measures how aligned they are.

Suppose

```text
Query = [2,1]

Key = [2,1]
```

Dot product

```text
2×2 +1×1

=

5
```

Large.

Very similar.

---

Another key

```text
[-2,-1]
```

Dot product

```text
2×(-2)+1×(-1)

=

-5
```

Very different.

So

```text
Query

↓

Compare with every Key

↓

Similarity Scores
```

---

# Masking

```python
tril = torch.tril(torch.ones(T,T))
```

Creates

```text
1 0 0 ...

1 1 0 ...

1 1 1 ...
```

---

Then

```python
wei = wei.masked_fill(tril==0,-inf)
```

Suppose

before masking

```text
2.1 5.3 1.4

4.2 3.1 8.8

...
```

After masking

```text
2.1  -∞  -∞

4.2 3.1  -∞

...
```

Future tokens disappear.

GPT cannot cheat.

---

# Softmax

```python
wei = F.softmax(wei,dim=-1)
```

Suppose

scores

```text
2

4

1
```

Softmax

might become

```text
0.11

0.82

0.07
```

Now

they become

probabilities.

Every row sums to

```text
1
```

---

# Values

```python
v = value(x)
```

Same idea as

Key

and

Query.

Input

```text
(4,8,32)
```

Output

```text
(4,8,16)
```

But now these vectors contain the **actual information** that will be passed to the next layer.

---

# Final Step

```python
out = wei @ v
```

Shapes:

```text
wei : (4,8,8)

v   : (4,8,16)
```

Multiply

```text
(8×8)

@

(8×16)

↓

(8×16)
```

Overall output

```text
(4,8,16)
```

---

# What does this multiplication mean?

Suppose Token 4 has attention weights

```text
0.10

0.60

0.20

0.10
```

Then

its output becomes

```text
0.10×Value(Token1)

+

0.60×Value(Token2)

+

0.20×Value(Token3)

+

0.10×Value(Token4)
```

In other words,

Token 4 **builds a new representation** by combining the information from the tokens it decided were important.

---

# Why don't we use `x` directly?

Notice Karpathy commented this line:

```python
# out = wei @ x
```

Instead he uses:

```python
out = wei @ v
```

Why?

Because the **Value projection** lets the model **learn what information should actually be shared**.

Imagine people in a meeting:

* **Query**: "What information do I need?"
* **Key**: "What topics can I help with?"
* **Value**: "Here's the detailed explanation."

You don't pass around everyone's entire raw brain (`x`). Each person first organizes their knowledge into a useful form (`v`), and that's what gets shared.

---

# The complete pipeline

```text
Input Tokens (x)
Shape: (4,8,32)
        │
        ├──────────────┬──────────────┐
        ▼              ▼              ▼
     Linear         Linear         Linear
      (Key)         (Query)        (Value)
        │              │              │
        ▼              ▼              ▼
 k (4,8,16)     q (4,8,16)     v (4,8,16)
        │              │
        └──────┬───────┘
               ▼
      q @ kᵀ  →  (4,8,8)
               │
               ▼
        Mask Future Tokens
               │
               ▼
           Softmax
               │
               ▼
    Attention Weights (4,8,8)
               │
               ▼
      Attention Weights @ Values
               │
               ▼
        Output (4,8,16)
```

## The single most important intuition

Forget the matrix multiplications for a moment. Self-attention is really just this conversation happening for **every token**:

```text
Current token:
"What kind of information am I looking for?"   ← Query

Previous tokens:
"Here's what I know."                          ← Key

Current token:
"Whose knowledge best matches my need?"        ← Query · Key

Softmax:
"These are the percentages I'll listen to."

Previous tokens:
"Here's my actual information."                ← Value

Current token:
"I'll combine that information into my new representation."
```

Everything else in this cell—linear layers, transposes, matrix multiplications—is simply an efficient way of performing that conversation **for every token in every sequence simultaneously on the GPU**. Once this intuition clicks, the rest of the Transformer architecture becomes much easier to understand.
