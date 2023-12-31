import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import datasets, transforms

# Load and preprocess MNIST dataset
transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.5,), (0.5,))
])
train_dataset = datasets.MNIST('data', train=True, download=True, transform=transform)
train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=64, shuffle=True)

class UNet(nn.Module):


    def __init__(self, in_channels, out_channels, num_layers=5):
        super().__init__()

        # Downsampling layers
        self.down_layers = nn.ModuleList()
        for i in range(num_layers):
            in_ch = in_channels if i == 0 else 2 ** (i - 1) * out_channels
            out_ch = 2 ** i * out_channels
            self.down_layers.append(
                nn.Sequential(
                    nn.Conv2d(in_ch, out_ch, kernel_size=3, padding=1),
                    nn.LeakyReLU(),
                    nn.Conv2d(out_ch, out_ch, kernel_size=3, padding=1),
                    nn.LeakyReLU(),
                    nn.MaxPool2d(2)
                )
            )

        # Bottleneck layer
        self.bottleneck = nn.Sequential(
            nn.Conv2d(2 ** (num_layers - 1) * out_channels, out_channels, kernel_size=3, padding=1),
            nn.LeakyReLU(),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1),
            nn.LeakyReLU()
        )

        # Upsampling layers
        self.up_layers = nn.ModuleList()
        for i in reversed(range(num_layers)):
            in_ch = out_channels * 2 if i == num_layers - 1 else 2 ** i * out_channels
            out_ch = 2 ** (i - 1) * out_channels
            self.up_layers.append(
                nn.Sequential(
                    nn.ConvTranspose2d(in_ch, out_ch, kernel_size=2, stride=2),
                    nn.LeakyReLU(),
                    nn.Conv2d(out_ch, out_ch, kernel_size=3, padding=1),
                    nn.LeakyReLU(),
                    nn.Conv2d(out_ch, out_ch, kernel_size=3, padding=1),
                    nn.LeakyReLU()
                )
            )

        # Output layer
        self.output_layer = nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1)

    def forward(self, x):
        # Downsampling
        down_outputs = []
        for layer in self.down_layers:
            x = layer(x)
            down_outputs.append(x)

        # Bottleneck
        x = self.bottleneck(x)

        # Upsampling
        for i, layer in enumerate(self.up_layers):
            x = layer(x)
            skip_connection = down_outputs[-(i + 1)]
            x = torch.cat([x, skip_connection], dim=1)

        # Output
        x = self.output_layer(x)
        return x

# Hyperparameters
diffusion_steps = 1000
beta_schedule = 'cosine'  # Cosine schedule for beta values

# Create model and optimizer
model = UNet()
optimizer = optim.Adam(model.parameters(), lr=1e-4)

# Define the forward_forward function
def forward_forward(model, X_left, X_right, y):
    # Split input data into two streams
    X_pos_left = X_left[y == 1]
    X_neg_left = X_left[y == 0]
    X_pos_right = X_right[y == 1]
    X_neg_right = X_right[y == 0]

    # Check if either tensor is empty
    if X_pos_left.nelement() == 0 or X_neg_left.nelement() == 0:
        return torch.tensor(0.0)

    # Compute forward pass of model on both streams
    out_pos = model(X_pos_left, X_pos_right)
    out_neg = model(X_neg_left, X_neg_right)

    # Compute loss
    loss = torch.mean((out_pos - out_neg)**2)
    return loss


# Training loop (adjusting for forward_forward)
for epoch in range(10):
    for batch_idx, (images, _) in enumerate(train_loader):
        # Divide images into left and right if needed (adjust based on model input)
        X_left, X_right = images[:, :, :14], images[:, :, 14:]  # Assuming 28x28 images

        # Forward pass through noise levels
        for t in range(diffusion_steps - 1, -1, -1):
            noise = torch.randn_like(images) * model.sqrt_alphas_cumprod[t]
            noisy_images = images * model.alphas_cumprod[t] + noise
            model_output = model(noisy_images, t)  # Obtain model output

            # Loss calculation using forward_forward
            loss = forward_forward(model, X_left, X_right, _)  # Assuming no labels

            # Backward pass and optimization
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            # Forward pass through noise levels for Codeblock2
            pred_noise = model(noisy_images, t)
            loss = torch.mean((pred_noise - noise) ** 2)

            # Backward pass and optimization for Codeblock2
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        # Print progress
        if batch_idx % 100 == 0:
            print('Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(
                epoch, batch_idx * len(images), len(train_loader.dataset),
                100. * batch_idx / len(train_loader), loss.item()))



# Noise Generation
def sample(model, noise, steps):
   """Generates samples using the diffusion model."""

   alphas = model.alphas_cumprod  # Access pre-calculated alphas
   sqrt_alphas_cumprod = model.sqrt_alphas_cumprod.to(noise.device)  # Ensure correct device placement

   # Iterate through diffusion steps
   for i in range(steps - 1, -1, -1):
       noise = model(noise, i) * sqrt_alphas_cumprod[i]  # Predict noise and rescale

   # Return generated samples
   return noise

# Generate samples and visualize
noise = torch.randn(64, 1, 28, 28)
samples = sample(model, noise, diffusion_steps)
