
```python
def forward(self, idx, targets=None):

    # idx and targets are both (B,T) tensor of integers
    logits = self.token_embedding_table(idx) # (B,T,C)

    if targets is None:
        loss = None
    else:
        B, T, C = logits.shape
        logits = logits.view(B*T, C)
        targets = targets.view(B*T)
        loss = F.cross_entropy(logits, targets)

    return logits, loss
```

---

# Step 1: What is `forward()`?

Think of a calculator.

You type

```
2 + 3
```

Calculator internally performs

```
Add numbers
↓

Return answer
```

Similarly,

when you do

```python
output = model(input)
```

PyTorch internally does

```python
output = model.forward(input)
```

So `forward()` simply answers the question

> **"How does the input travel through my model?"**

---

# Let's understand the inputs

The method receives

```python
idx
```

and

```python
targets
```

Let's use a tiny example.

Suppose our vocabulary is

```
0 -> h
1 -> e
2 -> l
3 -> o
```

Suppose our sentence is

```
hello
```

Tokenized as

```
h e l l o

↓

0 1 2 2 3
```

---

Now suppose our batch size is 2.

Input becomes

```python
idx =
[
 [0,1,2],
 [2,3,1]
]
```

Shape is

```
(B,T)

2 × 3
```

where

```
B = Batch Size

T = Sequence Length
```

Think of it like a classroom.

```
Student 1

0 1 2

Student 2

2 3 1
```

Each row is one training example.

---

# What are targets?

Remember the model predicts

```
Current Token

↓

Next Token
```

Suppose

Input

```
h e l
```

Target

```
e l l
```

So

```python
idx

[
 [0,1,2]
]
```

becomes

```python
targets

[
 [1,2,2]
]
```

Notice something.

```
Input

0 1 2

↓

Target

1 2 2
```

The targets are simply shifted one position to the left.

This is how language models learn.

---

# Now comes this line

```python
logits = self.token_embedding_table(idx)
```

This line confuses almost everyone initially.

Let's understand it visually.

Suppose our embedding table is

| Token | Prediction Scores |
| ----- | ----------------- |
| 0     | [2,4,1,0]         |
| 1     | [5,2,8,1]         |
| 2     | [3,6,2,9]         |
| 3     | [1,7,4,2]         |

Think of it as an Excel sheet.

```
Token 0

↓

Read Row 0
```

returns

```
[2,4,1,0]
```

Similarly

```
Token 2

↓

Read Row 2

↓

[3,6,2,9]
```

---

Now suppose

```python
idx =
[
 [0,1],
 [2,3]
]
```

PyTorch automatically does

```
0

↓

Row 0
```

```
1

↓

Row 1
```

```
2

↓

Row 2
```

```
3

↓

Row 3
```

and combines everything.

Result becomes

```
[
 [
   [2,4,1,0],
   [5,2,8,1]
 ],

 [
   [3,6,2,9],
   [1,7,4,2]
 ]
]
```

Did you notice?

Originally

```
2 × 2
```

Now

```
2 × 2 × 4
```

because every token became **4 prediction scores**.

---

# Why does shape become (B,T,C)?

Originally

```
idx

(B,T)
```

Example

```
2 × 3
```

```
[
 [0,1,2],
 [2,1,3]
]
```

Each number becomes

```
One vector

↓

[2,4,1,7]
```

Now every cell contains 4 numbers.

Shape becomes

```
(B,T,C)
```

where

```
B = batch size

T = sequence length

C = vocabulary size
```

So

```
2 × 3

↓

2 × 3 × 4
```

Think of it like this:

Before:

```
Student 1

0   1   2
```

After embedding:

```
Student 1

[2,4,1,0]

[5,1,8,3]

[7,9,0,2]
```

Each token has become a vector of scores.

---

# Why are they called logits?

Suppose the output vector is

```
[2,6,1,4]
```

These are **raw scores**.

They are **not probabilities**.

Later,

Softmax converts them into

```
[0.02,
 0.80,
 0.01,
 0.17]
```

So remember this pipeline:

```
Embedding

↓

Logits

↓

Softmax

↓

Probabilities
```

---

# Why check

```python
if targets is None:
```

Because the model has two jobs.

## Job 1: Training

During training

we already know the correct answer.

Example

```
Input

h

Correct answer

e
```

So we compute loss.

---

## Job 2: Prediction

Suppose you ask ChatGPT

```
Once upon a
```

There is **no correct answer**.

We only want prediction.

So

```
targets = None
```

Loss is unnecessary.

---

# Now the confusing part

```python
B, T, C = logits.shape
```

Suppose

```
logits.shape

(2,3,4)
```

Python automatically does

```python
B = 2
T = 3
C = 4
```

Nothing fancy.

Just unpacking.

---

# Why reshape?

Now we have

```
logits

2 × 3 × 4
```

Imagine this as:

```
Student 1

Token1

Prediction

Token2

Prediction

Token3

Prediction


Student2

Token1

Prediction

Token2

Prediction

Token3

Prediction
```

But `cross_entropy()` doesn't understand 3D tensors.

It expects

```
(Number of Examples,
 Number of Classes)
```

So we flatten everything.

---

# Understanding `view()`

Suppose you have this matrix:

```
1 2 3

4 5 6
```

Shape

```
2 × 3
```

If you reshape

```python
view(6)
```

You get

```
1 2 3 4 5 6
```

Same numbers.

Different arrangement.

Nothing changes.

Only the shape.

---

Here

```
2 × 3 × 4
```

becomes

```
6 × 4
```

because

```
2 × 3

=

6 predictions
```

Now every prediction becomes one training example.

---

# Targets are reshaped too

Originally

```
targets

2 × 3
```

Example

```
[
 [1,2,3],

 [0,1,2]
]
```

Flatten

```
1

2

3

0

1

2
```

Shape

```
6
```

Now

every row of logits

matches

one target.

---

# Finally

```python
loss = F.cross_entropy(logits, targets)
```

Let's understand what the model is actually doing.

Suppose one row of logits is

```
[2,8,1,3]
```

After softmax

```
A : 0.02

B : 0.90

C : 0.01

D : 0.07
```

Suppose correct answer is

```
B
```

Great!

Loss becomes small.

---

Suppose instead

```
A : 0.90

B : 0.01

C : 0.04

D : 0.05
```

Correct answer is still

```
B
```

The model was very confident—but confidently wrong.

Loss becomes very large.

Training then adjusts the embedding table so next time the score for `B` increases and the score for `A` decreases.

---

# The complete flow

Here's the whole `forward()` method as one pipeline:

```
Input Tokens (idx)
        │
        ▼
[
 [0,1,2],
 [2,3,1]
]
        │
        ▼
Embedding Lookup
        │
        ▼
Logits
Shape = (B,T,C)
        │
        ▼
Reshape to (B*T,C)
        │
        ▼
Compare with targets
        │
        ▼
Cross Entropy Loss
        │
        ▼
Return logits and loss
```

## A question to check your understanding

Suppose:

* `batch_size = 4`
* `sequence_length = 8`
* `vocab_size = 65`

Without looking at the code, try answering these:

1. What is the shape of `idx`?
2. What is the shape of `logits` immediately after `self.token_embedding_table(idx)`?
3. What is the shape of `logits` after `view(B*T, C)`?
4. What is the shape of `targets` after `view(B*T)`?

If you can answer those four questions confidently, you'll have understood the core tensor operations in the `forward()` method, which is one of the biggest hurdles when starting with PyTorch.
